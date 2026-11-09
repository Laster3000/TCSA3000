"""Conexiones MCP guardadas de TCSA3000 (varias a la vez).
Tipos:
- openai-tunel : Secure MCP Tunnel de OpenAI (ChatGPT "Conexion: Tunel"). Conexion SOLO saliente; un tunnel-client por conexion.
- cloudflare   : URL publica HTTPS (trycloudflare o host fijo) hacia la ruta secreta de la conexion.
- url-http     : URL local http://127.0.0.1:<puerto>/cx/<id>/<secreto>/mcp para clientes que hablan MCP por HTTP.
Autenticacion (lo que exige TCSA3000 en la ruta de la conexion):
- ninguna : la ruta secreta es la proteccion (tunel de OpenAI: nada expuesto a internet).
- token   : ademas exige 'Authorization: Bearer <token>' (credencial cifrada de la boveda).
- oauth   : se guarda la conexion, pero TCSA3000 aun NO emite tokens OAuth: la ruta responde 501 con explicacion.
Cada conexion tiene su propio secreto, permiso de escritura y arranque automatico. Nunca se muestran claves."""
from __future__ import annotations
import json, os, re, secrets as pysecrets, subprocess, threading, time, urllib.request
from pathlib import Path
from . import config, credenciales, openai_tunel, tunel
from .storage import journal, utc, write_json

TIPOS = ("openai-tunel", "cloudflare", "url-http")
AUTHS = ("ninguna", "token", "oauth")
CID = re.compile(r"[a-z0-9][a-z0-9-]{1,39}\Z")
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_procs: dict = {}      # id -> {"proc", "health", "url", "log"}
_lock = threading.Lock()

def _file() -> Path:
    return config.data_dir() / "conexiones.json"

def _guardar(lista: list):
    write_json(_file(), {"actualizado": utc(), "conexiones": lista})

def listar_crudo() -> list:
    f = _file()
    return json.loads(f.read_text("utf-8")).get("conexiones", []) if f.exists() else []

def migrar_desde_config(cfg: dict):
    """La configuracion antigua de un unico tunel (openaiTunnelId...) pasa a ser la primera conexion guardada."""
    if _file().exists() or not cfg.get("openaiTunnelId"):
        return
    _guardar([{"id": "chatgpt-tunel", "nombre": "ChatGPT · túnel seguro de OpenAI", "tipo": "openai-tunel", "auth": "ninguna",
               "tunnelId": cfg["openaiTunnelId"], "credencial": openai_tunel.CRED, "escritura": bool(cfg.get("openaiEscritura", True)),
               "alArrancar": bool(cfg.get("openaiTunelAlArrancar")), "transporte": cfg.get("openaiTransporte", "stdio"),
               "descripcion": "Migrada de la configuracion de un unico tunel", "creada": utc()}])

def obtener(cid: str) -> dict:
    c = next((x for x in listar_crudo() if x["id"] == cid), None)
    if not c: raise LookupError("CONEXION_NO_EXISTE:" + cid)
    return c

def secreto(cid: str) -> str:
    return credenciales.secreto_sistema("tcsa3000-cx-" + cid, "Ruta secreta local de la conexion " + cid)

def ruta_local(cfg: dict, cid: str) -> str:
    return "http://127.0.0.1:%d/cx/%s/%s/mcp" % (cfg["port"], cid, secreto(cid))

def guardar(datos: dict) -> dict:
    cid = (datos.get("id") or "").strip().lower()
    if not CID.fullmatch(cid): raise ValueError("ID_INVALIDO (minusculas, numeros y guiones)")
    tipo = datos.get("tipo"); auth = datos.get("auth", "ninguna")
    if tipo not in TIPOS: raise ValueError("TIPO_INVALIDO: " + ", ".join(TIPOS))
    if auth not in AUTHS: raise ValueError("AUTENTICACION_INVALIDA: " + ", ".join(AUTHS))
    if tipo == "openai-tunel" and not openai_tunel.TUNNEL_ID.fullmatch(datos.get("tunnelId", "")): raise ValueError("TUNNEL_ID_INVALIDO")
    lista = listar_crudo(); prev = next((x for x in lista if x["id"] == cid), {})
    c = dict(prev)
    for k in ("nombre", "tipo", "auth", "tunnelId", "tunelHost", "escritura", "alArrancar", "transporte", "descripcion"):
        if k in datos: c[k] = datos[k]
    c.update(id=cid, actualizada=utc()); c.setdefault("creada", utc()); c.setdefault("nombre", cid); c.setdefault("transporte", "stdio")
    c.setdefault("credencial", ("openai-runtime-" + cid) if tipo == "openai-tunel" else None)
    if datos.get("clave"):   # clave de runtime (OpenAI) -> boveda cifrada
        credenciales.guardar(c["credencial"] or ("openai-runtime-" + cid), datos["clave"].strip(), "Clave de runtime de la conexion " + cid)
    if auth == "token" and not credenciales.leer("tcsa3000-token-" + cid):
        credenciales.guardar("tcsa3000-token-" + cid, pysecrets.token_urlsafe(32), "Token Bearer de la conexion " + cid)
    lista = [x for x in lista if x["id"] != cid] + [c]; _guardar(lista)
    journal(config.data_dir() / "servicio.journal.jsonl", "CONEXION_GUARDADA", {"id": cid, "tipo": tipo, "auth": auth})
    return {"guardada": cid}

def borrar(cid: str) -> dict:
    parar(cid)
    lista = [x for x in listar_crudo() if x["id"] != cid]; _guardar(lista)
    journal(config.data_dir() / "servicio.journal.jsonl", "CONEXION_BORRADA", {"id": cid})
    return {"borrada": cid, "nota": "Las credenciales asociadas siguen en la boveda (puedes borrarlas en Credenciales)."}

def _vivo(cid) -> bool:
    p = _procs.get(cid); return bool(p and p["proc"].poll() is None)

def _listo(cid) -> bool:
    p = _procs.get(cid)
    if not p or p["proc"].poll() is not None: return False
    if not p.get("health"): return bool(p.get("url"))
    try:
        with urllib.request.urlopen(p["health"] + "readyz", timeout=2) as r: return r.status == 200
    except Exception: return False

def estado(cfg: dict) -> list:
    out = []
    for c in listar_crudo():
        cid = c["id"]; p = _procs.get(cid) or {}
        e = {k: c.get(k) for k in ("id", "nombre", "tipo", "auth", "tunnelId", "tunelHost", "escritura", "alArrancar", "transporte", "descripcion", "creada")}
        e.update(enMarcha=_vivo(cid), listo=_listo(cid), log=(p.get("log") or [])[-12:],
                 claveGuardada=bool(c.get("credencial") and credenciales.leer(c["credencial"])) if c["tipo"] == "openai-tunel" else None)
        if c["tipo"] == "url-http":
            e["url"] = ruta_local(cfg, cid)
        elif c["tipo"] == "cloudflare" and p.get("url"):
            e["url"] = p["url"].rstrip("/") + "/cx/%s/%s/mcp" % (cid, secreto(cid))
        if c["auth"] == "token":
            e["cabecera"] = "Authorization: Bearer " + (credenciales.leer("tcsa3000-token-" + cid) or "")
        if c["auth"] == "oauth":
            e["aviso"] = "OAuth guardado pero aun no disponible en TCSA3000: usa 'ninguna' (tunel de OpenAI) o 'token'."
        out.append(e)
    return out

def _leer(cid, proc):
    for line in iter(proc.stdout.readline, ""):
        with _lock:
            lg = _procs.get(cid, {}).setdefault("log", [])
            lg.append(re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "sk-****", line.strip())[-300:]); del lg[:-80]
            if "url" in _procs.get(cid, {}) and not _procs[cid]["url"]:
                m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
                if m: _procs[cid]["url"] = m.group(0)

def iniciar(cfg: dict, cid: str) -> dict:
    c = obtener(cid)
    if _vivo(cid): return {"estado": "YA_EN_MARCHA", "id": cid}
    if c["tipo"] == "url-http":
        return {"estado": "LISTA (no necesita proceso)", "url": ruta_local(cfg, cid)}
    if c["tipo"] == "openai-tunel":
        if not openai_tunel.exe().is_file(): return {"estado": "FALTA_TUNNEL_CLIENT", "ayuda": "Descarga tunnel-client (oficial de OpenAI) en Conectar una IA."}
        key = credenciales.leer(c.get("credencial") or "")
        if not key: return {"estado": "FALTA_CLAVE_RUNTIME", "ayuda": "Guarda la clave de runtime de esta conexion."}
        hp = openai_tunel._puerto_libre(); health = "http://127.0.0.1:%d/" % hp
        if c.get("transporte", "stdio") == "stdio":
            cmd = '"%s" -B "%s" --conexion %s' % (config.python_exe().replace("\\", "/"), Path(__file__).with_name("mcp_stdio.py").as_posix(), cid)
            enlace = ["--mcp.command", cmd]
        else:
            enlace = ["--mcp.server-url", "url=" + ruta_local(cfg, cid)]
        args = [str(openai_tunel.exe()), "run", "--control-plane.api-key", "env:CONTROL_PLANE_API_KEY", "--control-plane.tunnel-id", c["tunnelId"]] + \
               enlace + ["--health.listen-addr", "127.0.0.1:%d" % hp]
        env = dict(os.environ, CONTROL_PLANE_API_KEY=key, TCSA3000_HOME=str(config.home()), PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        cwd = str(openai_tunel.exe().parent)
    else:  # cloudflare
        if not tunel.exe().is_file(): return {"estado": "FALTA_CLOUDFLARED", "ayuda": "Descarga cloudflared en Conectar una IA."}
        health = None; env = dict(os.environ); cwd = str(tunel.exe().parent)
        if c.get("tunelHost"):
            tok = credenciales.leer("cloudflare-tunel-token")
            if not tok: return {"estado": "FALTA_CREDENCIAL cloudflare-tunel-token"}
            args = [str(tunel.exe()), "tunnel", "--no-autoupdate", "run", "--token", tok]
        else:
            args = [str(tunel.exe()), "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:%d" % cfg["port"]]
    proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", bufsize=1, env=env, creationflags=SIN_VENTANA, cwd=cwd)
    with _lock:
        _procs[cid] = {"proc": proc, "health": health, "log": [], "url": ("https://" + c["tunelHost"]) if c.get("tunelHost") else (None if c["tipo"] == "cloudflare" else "")}
    threading.Thread(target=_leer, args=(cid, proc), daemon=True).start()
    for _ in range(90):
        time.sleep(0.5)
        if proc.poll() is not None or _listo(cid): break
    st = next(e for e in estado(cfg) if e["id"] == cid)
    journal(config.data_dir() / "servicio.journal.jsonl", "CONEXION_INICIO", {"id": cid, "tipo": c["tipo"], "listo": st["listo"], "vivo": st["enMarcha"]})
    if not st["enMarcha"]:
        from . import historial
        historial.registrar_error("conexion:" + cid, "El proceso del tunel se cerro al arrancar", {"log": st["log"][-5:]})
        st["estado"] = "EL_PROCESO_SE_CERRO (mira el registro)"
    return st

def parar(cid: str) -> dict:
    with _lock:
        p = _procs.pop(cid, None)
    if p and p["proc"].poll() is None:
        p["proc"].terminate()
        try: p["proc"].wait(10)
        except subprocess.TimeoutExpired: p["proc"].kill()
    journal(config.data_dir() / "servicio.journal.jsonl", "CONEXION_PARADA", {"id": cid})
    return {"estado": "PARADA", "id": cid}

def parar_todas():
    for cid in list(_procs):
        try: parar(cid)
        except Exception: pass

def arrancar_automaticas(cfg: dict):
    for c in listar_crudo():
        if c.get("alArrancar"):
            try: iniciar(cfg, c["id"])
            except Exception as e:
                from . import historial
                historial.registrar_error("conexion:" + c["id"], str(e))

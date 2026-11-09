"""Secure MCP Tunnel de OpenAI para ChatGPT (Conexion: Tunel). Recomendado: conexion SOLO saliente hacia OpenAI; nada del PC
queda expuesto a internet y ChatGPT puede escribir (si su plan y el ajuste openaiEscritura lo permiten).
- tunnel-client oficial (github.com/openai/tunnel-client) descargado solo a peticion del usuario y verificado con SHA256SUMS.txt.
- tunnel_id (de platform.openai.com > Tunnels) en config openaiTunnelId; clave de runtime (Restricted: Tunnels Read+Use) cifrada
  con DPAPI como credencial openai-tunel-runtime. Se puede importar la que ya usaba MMC del Administrador de credenciales.
- El tunnel-client reenvia a http://127.0.0.1:<puerto>/openai/<secreto>/mcp (ruta local con secreto propio)."""
from __future__ import annotations
import ctypes, hashlib, io, json, os, re, socket, subprocess, threading, time, urllib.request, zipfile
from pathlib import Path
from . import config, credenciales
from .storage import journal, utc

API_LATEST = "https://api.github.com/repos/openai/tunnel-client/releases/latest"
REL = "https://github.com/openai/tunnel-client/releases/download/%s/%s"
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TUNNEL_ID = re.compile(r"tunnel_([a-z0-9]{4}_)?[a-z0-9]{32}\Z")
CRED = "openai-tunel-runtime"
_proc = None; _health = None; _log: list = []; _lock = threading.Lock()

def exe() -> Path:
    return config.home() / "tunel" / "openai" / "tunnel-client.exe"

def secreto() -> str:
    return credenciales.secreto_sistema("tcsa3000-openai", "Ruta secreta local para el Secure MCP Tunnel de OpenAI")

def _get(url: str, timeout=300) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "TCSA3000", "Accept": "application/octet-stream, application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def descargar() -> dict:
    """Descarga oficial (accion explicita del usuario) y verificacion SHA-256 contra SHA256SUMS.txt de la misma publicacion."""
    tag = json.loads(_get(API_LATEST, 60))["tag_name"]
    nombre = "tunnel-client-%s-windows-amd64.zip" % tag
    sums = _get(REL % (tag, "SHA256SUMS.txt"), 60).decode("utf-8", "replace")
    esperado = next((l.split()[0].lower() for l in sums.splitlines() if l.strip().endswith(nombre)), None)
    if not esperado:
        return {"estado": "RECHAZADO_SIN_SUMA", "version": tag}
    z = _get(REL % (tag, nombre))
    real = hashlib.sha256(z).hexdigest()
    if real != esperado:
        return {"estado": "RECHAZADO_SHA_NO_COINCIDE", "version": tag, "esperado": esperado, "real": real}
    with zipfile.ZipFile(io.BytesIO(z)) as zf:
        m = next((n for n in zf.namelist() if n.lower().endswith("tunnel-client.exe")), None)
        if not m: return {"estado": "RECHAZADO_ZIP_SIN_EXE", "version": tag}
        d = exe(); d.parent.mkdir(parents=True, exist_ok=True)
        tmp = d.with_name("tunnel-client.descarga"); tmp.write_bytes(zf.read(m)); os.replace(tmp, d)
    (d.parent / "VERSION.json").write_text(json.dumps({"version": tag, "zipSha256": real, "descargado": utc()}), "utf-8")
    journal(config.data_dir() / "servicio.journal.jsonl", "OPENAI_TUNEL_DESCARGA", {"version": tag, "sha256": real})
    return {"estado": "DESCARGADO", "version": tag, "sha256": real}

class _CRED(ctypes.Structure):
    _fields_ = [("Flags", ctypes.c_uint32), ("Type", ctypes.c_uint32), ("TargetName", ctypes.c_wchar_p), ("Comment", ctypes.c_wchar_p),
                ("LastWritten", ctypes.c_uint64), ("CredentialBlobSize", ctypes.c_uint32), ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
                ("Persist", ctypes.c_uint32), ("AttributeCount", ctypes.c_uint32), ("Attributes", ctypes.c_void_p),
                ("TargetAlias", ctypes.c_wchar_p), ("UserName", ctypes.c_wchar_p)]

def importar_de_windows(objetivo: str = "MMC55.AI.TUNNEL.RUNTIME", destino: str = CRED) -> dict:
    """Copia (accion del usuario) la clave de runtime guardada en el Administrador de credenciales a la boveda DPAPI de TCSA3000.
    No modifica la credencial original."""
    if os.name != "nt": return {"estado": "SOLO_WINDOWS"}
    p = ctypes.POINTER(_CRED)()
    if not ctypes.windll.advapi32.CredReadW(objetivo, 1, 0, ctypes.byref(p)):
        return {"estado": "NO_ENCONTRADA", "objetivo": objetivo}
    try:
        b = bytes(p.contents.CredentialBlob[:p.contents.CredentialBlobSize])
    finally:
        ctypes.windll.advapi32.CredFree(p)
    val = None
    for enc in ("utf-16-le", "utf-8"):
        try:
            t = b.decode(enc).strip("\x00").strip()
            if t.startswith("sk-") or (len(t) > 20 and t.isprintable()): val = t; break
        except UnicodeDecodeError:
            pass
    if not val: return {"estado": "FORMATO_NO_RECONOCIDO", "objetivo": objetivo}
    credenciales.guardar(destino, val, "Clave de runtime del Secure MCP Tunnel (importada de %s)" % objetivo)
    return {"estado": "IMPORTADA", "desde": objetivo, "credencial": destino}

def _puerto_libre() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

def _listo() -> bool:
    if not _health: return False
    try:
        with urllib.request.urlopen(_health + "readyz", timeout=2) as r: return r.status == 200
    except Exception:
        return False

def estado(cfg: dict) -> dict:
    with _lock:
        vivo = _proc is not None and _proc.poll() is None
    v = exe().parent / "VERSION.json"
    return {"instalado": exe().is_file(), "version": json.loads(v.read_text("utf-8")).get("version") if v.is_file() else None,
            "tunnelId": cfg.get("openaiTunnelId") or "", "claveGuardada": credenciales.leer(CRED) is not None if os.name == "nt" else False,
            "enMarcha": vivo, "listo": vivo and _listo(), "panelCliente": (_health + "ui") if (vivo and _health) else None,
            "escrituraChatGPT": bool(cfg.get("openaiEscritura", True)), "transporte": cfg.get("openaiTransporte", "stdio"), "log": _log[-10:]}

def _leer(proc):
    for line in iter(proc.stdout.readline, ""):
        with _lock:
            _log.append(re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "sk-****", line.strip())[-300:]); del _log[:-60]

def iniciar(cfg: dict) -> dict:
    global _proc, _health
    tid = (cfg.get("openaiTunnelId") or "").strip()
    if not exe().is_file(): return {"estado": "FALTA_TUNNEL_CLIENT", "ayuda": "Pulsa 'Descargar tunnel-client (oficial de OpenAI)'."}
    if not TUNNEL_ID.fullmatch(tid): return {"estado": "FALTA_TUNNEL_ID", "ayuda": "Pega el tunnel_id (platform.openai.com > Settings > Tunnels)."}
    key = credenciales.leer(CRED)
    if not key: return {"estado": "FALTA_CLAVE_RUNTIME", "ayuda": "Guarda la clave de runtime (Restricted: Tunnels Read + Use) o importala."}
    with _lock:
        if _proc is not None and _proc.poll() is None: return {"estado": "YA_EN_MARCHA"}
        hp = _puerto_libre(); _health = "http://127.0.0.1:%d/" % hp; _log.clear()
        transporte = str(cfg.get("openaiTransporte", "stdio")).lower()
        if transporte == "stdio":
            # Usa el adaptador stdio existente y la ruta privada OpenAI en el servicio.
            # Evita trabajadores HTTP bloqueados; mantiene openaiEscritura y la concesion TCSA.
            script = Path(__file__).with_name("mcp_stdio.py")
            comando = '"%s" -B "%s" --openai' % (
                config.python_exe().replace("\\", "/"), script.as_posix())
            enlace = ["--mcp.command", comando]
        elif transporte == "http":
            # Reversion controlada al transporte anterior, sin cambiar tunnel_id ni claves.
            url = "http://127.0.0.1:%d/openai/%s/mcp" % (cfg["port"], secreto())
            enlace = ["--mcp.server-url", "url=" + url]
        else:
            return {"estado": "TRANSPORTE_INVALIDO", "transporte": transporte}
        env = dict(os.environ, CONTROL_PLANE_API_KEY=key)
        orden = [str(exe()), "run", "--control-plane.api-key", "env:CONTROL_PLANE_API_KEY",
                 "--control-plane.tunnel-id", tid] + enlace + [
                 "--health.listen-addr", "127.0.0.1:%d" % hp]
        _proc = subprocess.Popen(orden, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace", bufsize=1,
                                 env=env, creationflags=SIN_VENTANA, cwd=str(exe().parent))
    threading.Thread(target=_leer, args=(_proc,), daemon=True).start()
    for _ in range(90):
        time.sleep(0.5)
        if _proc.poll() is not None or _listo(): break
    st = estado(cfg)
    journal(config.data_dir() / "servicio.journal.jsonl", "OPENAI_TUNEL_INICIO", {"tunnelId": tid, "listo": st["listo"], "vivo": st["enMarcha"]})
    if not st["enMarcha"]: st["estado"] = "EL_CLIENTE_SE_CERRO (mira el registro)"
    return st

def parar(cfg: dict | None = None) -> dict:
    global _proc
    with _lock:
        if _proc is not None and _proc.poll() is None:
            _proc.terminate()
            try: _proc.wait(10)
            except subprocess.TimeoutExpired: _proc.kill()
        _proc = None
    journal(config.data_dir() / "servicio.journal.jsonl", "OPENAI_TUNEL_PARADA", {})
    return {"estado": "PARADO"}

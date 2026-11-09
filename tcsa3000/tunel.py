"""Tunel HTTPS seguro para IAs remotas (ChatGPT) con cloudflared.
- Expone SOLO la ruta /remoto/<secreto>/mcp del servicio local; el resto exige token local y Origin local.
- Secreto largo aleatorio guardado con DPAPI (credencial de sistema tcsa3000-remoto); se puede rotar.
- Solo lectura por defecto (config remotoEscritura=false).
- Modo rapido (trycloudflare, URL cambia en cada arranque) o fijo (credencial cloudflare-tunel-token + config tunelHost).
- cloudflared.exe se descarga SOLO cuando el usuario lo pide desde el menu, de la publicacion oficial de Cloudflare, y se
  comprueba su firma Authenticode antes de usarlo."""
from __future__ import annotations
import json, os, re, subprocess, threading, time, urllib.request
from pathlib import Path
from . import config, credenciales
from .storage import journal, utc

URL_DESCARGA = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_proc = None
_url = None
_log: list = []
_lock = threading.Lock()

def exe() -> Path:
    return config.home() / "tunel" / "cloudflared.exe"

def secreto() -> str:
    return credenciales.secreto_sistema("tcsa3000-remoto", "Ruta secreta del MCP remoto (tunel)")

def rotar_secreto() -> dict:
    credenciales.secreto_sistema("tcsa3000-remoto", "Ruta secreta del MCP remoto (tunel)", rotar=True)
    return {"rotado": True, "aviso": "Actualiza la URL en ChatGPT: la anterior deja de funcionar."}

def firma(p: Path) -> dict:
    if os.name != "nt":
        return {"valida": False, "motivo": "SOLO_WINDOWS"}
    q = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "$s=Get-AuthenticodeSignature -LiteralPath '%s'; $s.Status.ToString(); $s.SignerCertificate.Subject" % str(p).replace("'", "''")],
                       capture_output=True, text=True, timeout=60, creationflags=SIN_VENTANA).stdout.splitlines()
    estado = q[0].strip() if q else ""; sujeto = q[1].strip() if len(q) > 1 else ""
    return {"valida": estado == "Valid" and "Cloudflare" in sujeto, "estado": estado, "firmante": sujeto}

def descargar() -> dict:
    """Descarga oficial de cloudflared (accion explicita del usuario)."""
    d = exe(); d.parent.mkdir(parents=True, exist_ok=True)
    tmp = d.with_name("cloudflared.descarga")
    with urllib.request.urlopen(URL_DESCARGA, timeout=300) as r, open(tmp, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b: break
            f.write(b)
    fz = firma(tmp)
    if not fz["valida"]:
        bad = d.with_name("cloudflared-RECHAZADO-" + utc().replace(":", "")[:17] + ".exe"); os.replace(tmp, bad)
        return {"estado": "RECHAZADO_FIRMA_NO_VALIDA", "firma": fz, "fichero": str(bad)}
    os.replace(tmp, d)
    journal(config.data_dir() / "servicio.journal.jsonl", "TUNEL_DESCARGA", {"firma": fz, "bytes": d.stat().st_size})
    return {"estado": "DESCARGADO", "firma": fz, "bytes": d.stat().st_size}

def estado(cfg: dict) -> dict:
    with _lock:
        vivo = _proc is not None and _proc.poll() is None
        return {"instalado": exe().is_file(), "enMarcha": vivo, "urlPublica": _url if vivo else None,
                "urlMCP": (_url.rstrip("/") + "/remoto/" + secreto() + "/mcp") if (vivo and _url) else None,
                "modo": "FIJO" if cfg.get("tunelHost") else "RAPIDO (la URL cambia en cada arranque)",
                "escrituraRemota": bool(cfg.get("remotoEscritura")), "log": _log[-8:]}

def _leer(proc):
    global _url
    for line in iter(proc.stderr.readline, ""):
        line = line.strip()
        with _lock:
            _log.append(line[-300:]); del _log[:-50]
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m and not _url:
                _url = m.group(0)

def iniciar(cfg: dict) -> dict:
    global _proc, _url
    if not exe().is_file():
        return {"estado": "FALTA_CLOUDFLARED", "ayuda": "Pulsa 'Descargar cloudflared' (oficial de Cloudflare)."}
    fz = firma(exe())
    if os.name == "nt" and not fz["valida"]:
        return {"estado": "BLOQUEADO_FIRMA_NO_VALIDA", "firma": fz}
    with _lock:
        if _proc is not None and _proc.poll() is None:
            return {"estado": "YA_EN_MARCHA"}
        _url = None; _log.clear()
        tok = credenciales.leer("cloudflare-tunel-token") if cfg.get("tunelHost") else None
        if cfg.get("tunelHost"):
            if not tok: return {"estado": "FALTA_CREDENCIAL cloudflare-tunel-token"}
            args = [str(exe()), "tunnel", "--no-autoupdate", "run", "--token", tok]
            _url = "https://" + cfg["tunelHost"].strip("/")
        else:
            args = [str(exe()), "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:%d" % cfg["port"]]
        _proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                                 creationflags=SIN_VENTANA, cwd=str(exe().parent))
    threading.Thread(target=_leer, args=(_proc,), daemon=True).start()
    for _ in range(60):
        time.sleep(0.5)
        with _lock:
            if _url or _proc.poll() is not None: break
    journal(config.data_dir() / "servicio.journal.jsonl", "TUNEL_INICIO", {"url": _url, "vivo": _proc.poll() is None})
    return estado(cfg)

def parar(cfg: dict) -> dict:
    global _proc, _url
    with _lock:
        if _proc is not None and _proc.poll() is None:
            _proc.terminate()
            try: _proc.wait(10)
            except subprocess.TimeoutExpired: _proc.kill()
        _proc = None; _url = None
    journal(config.data_dir() / "servicio.journal.jsonl", "TUNEL_PARADA", {})
    return {"estado": "PARADO"}

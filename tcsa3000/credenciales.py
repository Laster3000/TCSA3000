"""Credenciales cifradas con DPAPI (usuario actual de Windows). Nunca se devuelven por la API ni se exportan."""
from __future__ import annotations
import base64, ctypes, json, os, re, subprocess, secrets as pysecrets
from pathlib import Path
from . import config
from .storage import write_json, utc

NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,63}\Z")

class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]

def _dpapi(data: bytes, protect: bool) -> bytes:
    if os.name != "nt":
        raise OSError("DPAPI_SOLO_WINDOWS")
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    buf = ctypes.create_string_buffer(data, len(data))
    inp = _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))); out = _BLOB()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(inp), None, None, None, None, 0x1, ctypes.byref(out)):  # CRYPTPROTECT_UI_FORBIDDEN
        raise OSError("DPAPI_FALLO")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)

def _file():
    return config.data_dir() / "credenciales.dpapi.json"

def _load() -> dict:
    f = _file()
    return json.loads(f.read_text("utf-8")) if f.exists() else {}

def guardar(nombre: str, valor: str, descripcion: str = "") -> dict:
    if not NAME.fullmatch(nombre or "") or not valor:
        raise ValueError("CREDENCIAL_INVALIDA")
    d = _load()
    d[nombre] = {"cifrado": base64.b64encode(_dpapi(valor.encode("utf-8"), True)).decode(), "descripcion": descripcion[:200], "actualizado": utc()}
    write_json(_file(), d)
    return {"nombre": nombre, "guardado": True}

def leer(nombre: str) -> str | None:
    rec = _load().get(nombre)
    return _dpapi(base64.b64decode(rec["cifrado"]), False).decode("utf-8") if rec else None

SISTEMA = ("tcsa3000-servicio", "tcsa3000-remoto", "tcsa3000-openai")
PREFIJOS_SISTEMA = ("tcsa3000-cx-",)

def listar() -> list:
    return [{"nombre": k, "descripcion": v.get("descripcion", ""), "actualizado": v.get("actualizado"), "valor": "********",
             "sistema": k in SISTEMA or k.startswith(PREFIJOS_SISTEMA)} for k, v in sorted(_load().items())]

def borrar(nombre: str) -> dict:
    if nombre in SISTEMA or nombre.startswith(PREFIJOS_SISTEMA):
        raise PermissionError("CREDENCIAL_DE_SISTEMA: no se borra (usa 'Rotar' para cambiarla)")
    d = _load(); existed = d.pop(nombre, None) is not None; write_json(_file(), d)
    return {"nombre": nombre, "borrado": existed}

def secreto_sistema(nombre: str, descripcion: str, rotar: bool = False) -> str:
    t = None if rotar else leer(nombre)
    if not t:
        t = pysecrets.token_urlsafe(32); guardar(nombre, t, descripcion)
    return t

PAT = re.compile(r"(TOKEN|KEY|SECRET|PASS|PWD|AUTH|CRED|BEARER)", re.I)

def _mask_env(env: dict) -> list:
    return [{"variable": k, "pareceSecreto": bool(PAT.search(k)), "valor": "********" if PAT.search(k) else "(no secreto)"} for k in sorted(env or {})]

def _json(p: Path):
    try: return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError): return None

def inventario(catalogo_raices: list | None = None) -> dict:
    """Mapa de DONDE hay credenciales en este PC, solo con nombres (nunca valores)."""
    home = Path.home(); la = Path(os.environ.get("LOCALAPPDATA", home)); ap = Path(os.environ.get("APPDATA", home))
    out = {"aviso": "Solo nombres y ubicaciones. Ningun valor se lee para mostrarlo ni sale de este PC.", "secciones": []}
    out["secciones"].append({"sitio": "Boveda de TCSA3000 (DPAPI)", "ruta": str(_file()), "elementos": [
        {"nombre": x["nombre"], "detalle": x["descripcion"] + (" · de sistema" if x["sistema"] else "")} for x in listar()]})
    clientes = [("Claude Desktop", p) for p in sorted(la.glob("Claude-Data/claude_*/claude_desktop_config.json"))] + \
               [("Claude Desktop", ap / "Claude" / "claude_desktop_config.json"), ("Cursor", home / ".cursor" / "mcp.json"),
                ("Gemini CLI", home / ".gemini" / "settings.json"), ("VS Code", ap / "Code" / "User" / "mcp.json"), ("Claude Code", home / ".claude.json")]
    for nombre, p in clientes:
        d = _json(p) if p.is_file() else None
        if not isinstance(d, dict): continue
        srv = d.get("mcpServers") or d.get("servers") or {}
        els = []
        for k, v in sorted(srv.items()):
            env = (v or {}).get("env") or {}; hdr = (v or {}).get("headers") or {}
            els.append({"nombre": "MCP " + k, "detalle": ", ".join(e["variable"] + ("=****" if e["pareceSecreto"] else "") for e in _mask_env(env)) or
                        ("cabeceras: " + ", ".join(sorted(hdr)) if hdr else "sin variables")})
        out["secciones"].append({"sitio": nombre, "ruta": str(p), "elementos": els})
    codex = home / ".codex" / "config.toml"
    if codex.is_file():
        txt = codex.read_text("utf-8", errors="replace")
        out["secciones"].append({"sitio": "Codex", "ruta": str(codex), "elementos": [{"nombre": "MCP " + m, "detalle": "servidor configurado"} for m in re.findall(r"\[mcp_servers\.([^\].]+)\]", txt)]})
    envs = [k for k in os.environ if PAT.search(k)]
    out["secciones"].append({"sitio": "Variables de entorno (proceso actual)", "ruta": "entorno de Windows", "elementos": [{"nombre": k, "detalle": "valor oculto"} for k in sorted(envs)]})
    if os.name == "nt":
        try:
            q = subprocess.run(["cmdkey", "/list"], capture_output=True, text=True, timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            objs = [l.split(":", 1)[1].strip() for l in q.splitlines() if ":" in l and l.strip().lower().startswith(("target", "destino"))]
            out["secciones"].append({"sitio": "Administrador de credenciales de Windows", "ruta": "cmdkey /list", "elementos": [{"nombre": o, "detalle": "credencial guardada"} for o in objs]})
        except (OSError, subprocess.SubprocessError):
            pass
    otros = [("Git (credenciales en texto)", home / ".git-credentials"), ("GitHub CLI", home / ".config" / "gh" / "hosts.yml"), ("GitHub CLI", ap / "GitHub CLI" / "hosts.yml"),
             ("Cloudflare (cloudflared)", home / ".cloudflared"), ("ngrok", la / "ngrok" / "ngrok.yml"), ("npm", home / ".npmrc"), ("Python pip", ap / "pip" / "pip.ini")]
    els = [{"nombre": n, "detalle": str(p)} for n, p in otros if p.exists()]
    out["secciones"].append({"sitio": "Otras herramientas con posibles credenciales", "ruta": "carpeta de usuario", "elementos": els})
    envf = []
    for raiz in (catalogo_raices or []):
        try:
            for f in Path(raiz).glob(".env*"):
                if f.is_file():
                    claves = [l.split("=", 1)[0].strip() for l in f.read_text("utf-8", errors="replace").splitlines() if "=" in l and not l.strip().startswith("#")]
                    envf.append({"nombre": str(f), "detalle": "claves: " + ", ".join(claves[:20])})
        except OSError:
            pass
    out["secciones"].append({"sitio": "Ficheros .env de los proyectos", "ruta": "raices del catalogo", "elementos": envf})
    out["secciones"].append({"sitio": "Conectores en la nube (claude.ai / ChatGPT)", "ruta": "gestionados por cada servicio",
                             "elementos": [{"nombre": "GitHub, Google Drive y otros conectores", "detalle": "sus credenciales viven en claude.ai/ChatGPT; no son visibles desde este PC"}]})
    return out

def token_servicio() -> str:
    """Token local del servicio (lo usan bandeja, panel y adaptador MCP del mismo usuario)."""
    t = leer("tcsa3000-servicio")
    if not t:
        t = pysecrets.token_urlsafe(32); guardar("tcsa3000-servicio", t, "Token local del servicio TCSA3000")
    return t

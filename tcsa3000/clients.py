"""Alta/baja del MCP de TCSA3000 en clientes. Siempre con preimagen (.bak) y sin tocar otras entradas."""
from __future__ import annotations
import json, os, shutil
from pathlib import Path
from . import config
from .storage import atomic_write, utc

SERVER = "tcsa3000"

def claude_configs() -> list:
    out = []
    la, ap = os.environ.get("LOCALAPPDATA"), os.environ.get("APPDATA")
    if la:
        out += sorted(Path(la, "Claude-Data").glob("claude_*/claude_desktop_config.json"))
    if ap and Path(ap, "Claude", "claude_desktop_config.json").exists():
        out.append(Path(ap, "Claude", "claude_desktop_config.json"))
    return out

def entry() -> dict:
    h = config.home()
    return {"command": config.python_exe(False), "args": ["-B", str(h / "tcsa3000" / "mcp_stdio.py")], "env": {"TCSA3000_HOME": str(h)}}

def registrar(path: Path, quitar: bool = False) -> dict:
    path = Path(path)
    cfg = json.loads(path.read_text("utf-8-sig")) if path.exists() else {}
    if not isinstance(cfg, dict):
        raise ValueError("CONFIG_CLIENTE_NO_ES_OBJETO")
    if path.exists():
        bak = path.with_name(path.name + ".bak-tcsa3000-" + utc().replace(":", "").replace("-", "")[:15])
        shutil.copy2(path, bak)
    else:
        bak = None
    servers = cfg.setdefault("mcpServers", {})
    if quitar:
        servers.pop(SERVER, None)
    else:
        servers[SERVER] = entry()
    atomic_write(path, (json.dumps(cfg, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return {"cliente": str(path), "accion": "BAJA" if quitar else "ALTA", "preimagen": str(bak) if bak else None,
            "aviso": "Cierra la app de Claude por completo antes y vuelve a abrirla despues; si esta abierta puede sobrescribir el archivo."}

def bootstrap_web() -> str:
    """Texto para IAs sin MCP local (ChatGPT/Claude web): leen el TCSA y el respaldo de TCSA3000 en Drive."""
    return ("TCSA | ARRANQUE CON TCSA3000\n"
            "Si tienes la herramienta MCP tcsa3000: llama primero a tcsa3000_arranque y sigue sus indicaciones "
            "(abrir_proyecto -> trabajo -> cierre C1/C2 -> soltar_proyecto).\n"
            "Si NO la tienes: en Google Drive, carpeta TCSA, lee INSTRUCCIONES-MAESTRAS.md + MANIFEST-INSTRUCCIONES.json, "
            "LEEME-PRIMERO.md y 03-PROYECTOS/TCSA3000/ESTADO-FALLBACK/CONTEXTO-TCSA3000.md (menu, proyectos, LISTA y DESCUBRIMIENTOS). "
            "Del proyecto pedido lee solo su capsula y 00-CHECKPOINTS/BY-PROJECT/<ID>/LATEST.json. "
            "Para guardar sin MCP crea un fichero NUEVO en 00-CHECKPOINTS/BY-PROJECT/<ID>/CIERRES/ y no sobrescribas indices. "
            "Respeta LEASE.json (un agente por proyecto). No repetir SUCCEEDED; reconciliar UNKNOWN. Sin lectura remota: PENDING_SYNC.\n")

def snippet(token: str | None = None, port: int | None = None) -> dict:
    """Configuracion lista para copiar en cualquier cliente MCP."""
    e = entry(); cmd, args, home = e["command"], e["args"], e["env"]["TCSA3000_HOME"]
    out = {
        "claude_desktop_json": {"mcpServers": {SERVER: e}},
        "claude_code_comando": "claude mcp add %s --scope user -e TCSA3000_HOME=\"%s\" -- \"%s\" %s" % (SERVER, home, cmd, " ".join('"%s"' % a for a in args)),
        "codex_config_toml": '[mcp_servers.%s]\ncommand = %s\nargs = %s\nenv = { TCSA3000_HOME = %s }\n' % (SERVER, json.dumps(cmd), json.dumps(args), json.dumps(home)),
        "cursor_windsurf_gemini_json": {"mcpServers": {SERVER: e}},
        "vscode_mcp_json": {"servers": {SERVER: dict(e, type="stdio")}},
        "ia_web_sin_mcp": bootstrap_web(),
    }
    if token and port:
        out["http_streamable"] = {"url": "http://127.0.0.1:%d/mcp" % port, "headers": {"X-TCSA3000-Token": token},
                                  "nota": "Solo en este PC. El token es secreto local: no lo compartas ni lo subas."}
    return out

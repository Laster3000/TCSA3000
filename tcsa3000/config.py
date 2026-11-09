"""Configuracion. Raiz = TCSA3000_HOME o la carpeta que contiene este paquete (se puede mover)."""
from __future__ import annotations
import json, os, sys
from pathlib import Path

DEFAULTS = {
    "tcsaRoot": r"G:\Mi unidad\TCSA",
    "fallbackDir": r"G:\Mi unidad\TCSA\03-PROYECTOS\TCSA3000\ESTADO-FALLBACK",
    "host": "127.0.0.1",
    "port": 18730,
    "fallbackEveryMinutes": 10,
    "allowlist": [
        {"projectId": "TCSA-CORE", "path": "INSTRUCCIONES-MAESTRAS.md"},
        {"projectId": "TCSA-CORE", "path": "LEEME-PRIMERO.md"},
        {"projectId": "TCSA-CORE", "path": "02-CATALOGO/PROYECTOS.json"},
        {"projectId": "TCSA-CORE", "path": "08-DESCUBRIMIENTOS/INDEX.json"},
        {"projectId": "TCSA-CORE", "path": "07-LISTA/INDEX.json"},
        {"projectId": "TCSA3000", "path": "03-PROYECTOS/TCSA3000/CAPSULA-PROYECTO.json"},
    ],
}

def home() -> Path:
    env = os.environ.get("TCSA3000_HOME")
    return Path(env).resolve() if env else Path(__file__).resolve().parents[1]

def config_path() -> Path:
    return home() / "tcsa3000.config.json"

def load() -> dict:
    cfg = dict(DEFAULTS)
    p = config_path()
    if p.is_file():
        user = json.loads(p.read_text("utf-8-sig"))
        if not isinstance(user, dict):
            raise ValueError("CONFIG_NOT_OBJECT")
        cfg.update(user)
    cfg["home"] = str(home())
    if not isinstance(cfg["port"], int) or not 1024 <= cfg["port"] <= 65535:
        raise ValueError("CONFIG_PORT_INVALID")
    if cfg["host"] not in ("127.0.0.1", "localhost"):
        raise ValueError("CONFIG_HOST_MUST_BE_LOCAL")
    return cfg

def data_dir() -> Path:
    d = home() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d

def python_exe(windowless: bool = False) -> str:
    exe = Path(sys.executable)
    if not windowless and exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").exists():
        return str(exe.parent / "python.exe")  # los clientes MCP necesitan stdio de consola
    if windowless and exe.name.lower() == "python.exe" and (exe.parent / "pythonw.exe").exists():
        return str(exe.parent / "pythonw.exe")
    return str(exe)

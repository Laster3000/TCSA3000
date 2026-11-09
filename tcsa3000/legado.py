"""Reutiliza las herramientas EXISTENTES del TCSA tal cual (sin copiarlas ni modificarlas):
00-CHECKPOINTS/REANUDAR-PROYECTO.py, 06-EXPORT-PUBLICO/tools/route_work.py y archive_search.py."""
from __future__ import annotations
import importlib.util
from pathlib import Path

_cache: dict = {}

def cargar(cfg: dict, rel: str, nombre: str):
    p = Path(cfg["tcsaRoot"]) / rel
    if not p.is_file():
        raise FileNotFoundError("HERRAMIENTA_TCSA_NO_ACCESIBLE:" + rel)
    key = (str(p), p.stat().st_mtime_ns)
    if key not in _cache:
        spec = importlib.util.spec_from_file_location("tcsa_legado_" + nombre, p)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        _cache[key] = m
    return _cache[key]

def reanudador(cfg: dict):
    m = cargar(cfg, "00-CHECKPOINTS/REANUDAR-PROYECTO.py", "reanudar")
    root = Path(cfg["tcsaRoot"]); m.ROOT = root; m.CATALOG = root / "02-CATALOGO" / "PROYECTOS.json"
    return m

def enrutador(cfg: dict):
    return cargar(cfg, "06-EXPORT-PUBLICO/tools/route_work.py", "route_work")

def archivo_historico(cfg: dict):
    return cargar(cfg, "06-EXPORT-PUBLICO/tools/archive_search.py", "archive_search")

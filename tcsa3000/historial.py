"""Historial de TCSA3000: una sola vista de lo que ha pasado (arranques, tuneles, respaldos, escrituras, llamadas remotas)
y sobre todo de los FALLOS, para poder revisarlos desde el menu. Solo lectura de los diarios; los errores se anotan en
data/errores.jsonl (append, con rotacion simple)."""
from __future__ import annotations
import json, threading
from pathlib import Path
from . import config
from .storage import utc

_lock = threading.Lock()
FUENTES = {"servicio": "servicio.journal.jsonl", "continuidad": "continuidad.journal.jsonl", "remoto": "remoto.journal.jsonl",
           "normas": "normas.journal.jsonl", "errores": "errores.jsonl"}
MALO = ("ERROR", "FALLO", "BLOQUE", "RECHAZ", "CONFLICT", "PARCIAL", "INVALID", "NO_ARRANCO", "TIMEOUT", "EXCEPTION")

def registrar_error(origen: str, mensaje: str, detalle: dict | None = None):
    p = config.data_dir() / "errores.jsonl"
    row = {"at": utc(), "op": "ERROR", "origen": origen[:60], "mensaje": str(mensaje)[:800], "detail": detalle or {}}
    with _lock:
        try:
            if p.exists() and p.stat().st_size > 2_000_000:
                p.replace(p.with_name("errores.anterior.jsonl"))
            with open(p, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError:
            pass

def _valores(x):
    if isinstance(x, dict):
        for v in x.values(): yield from _valores(v)
    elif isinstance(x, list):
        for v in x: yield from _valores(v)
    elif x is not None:
        yield str(x)

def _es_fallo(e: dict) -> bool:
    d = e.get("detail") or {}
    if e.get("op") == "ERROR" or e.get("ok") is False or d.get("ok") is False:
        return True
    if d.get("ok") is True:
        return False
    if isinstance(d.get("espejo"), dict) and d["espejo"].get("estado") == "OK" and (d.get("github") or {}).get("estado") in (None, "OK"):
        return False
    t = (e.get("op", "") + " " + " ".join(_valores(d))).upper()   # solo valores: las claves ("error": null) no cuentan
    return any(m in t for m in MALO)

def _ultimas(p: Path, n: int) -> list:
    if not p.is_file():
        return []
    with open(p, "rb") as f:
        f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 600_000))
        lines = f.read().decode("utf-8", "replace").splitlines()[-n:]
    out = []
    for l in lines:
        try: out.append(json.loads(l))
        except ValueError: pass
    return out

def leer(solo_fallos: bool = False, fuente: str = "", texto: str = "", limite: int = 300) -> dict:
    d = config.data_dir(); ev = []
    for nombre, fich in FUENTES.items():
        if fuente and fuente != nombre: continue
        for e in _ultimas(d / fich, 2000):
            e = dict(e); e["fuente"] = nombre; e["fallo"] = _es_fallo(e); ev.append(e)
    if not fuente or fuente == "bandeja":
        b = d / "bandeja.log"
        if b.is_file():
            for l in b.read_text("utf-8", errors="replace").splitlines()[-500:]:
                ev.append({"at": l[:19], "op": "BANDEJA", "detail": {"texto": l[20:300]}, "fuente": "bandeja", "fallo": any(m in l.upper() for m in MALO)})
    t = (texto or "").lower()
    ev = [e for e in ev if (not solo_fallos or e["fallo"]) and (not t or t in json.dumps(e, ensure_ascii=False).lower())]
    ev.sort(key=lambda e: e.get("at", ""), reverse=True)
    total_fallos = sum(1 for e in ev if e["fallo"])
    return {"eventos": ev[:max(1, min(int(limite), 1000))], "fallos": total_fallos, "total": len(ev),
            "nota": "Horas en UTC. Fuentes: " + ", ".join(list(FUENTES) + ["bandeja"])}

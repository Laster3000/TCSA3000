"""Normas/directrices PROPIAS de TCSA3000 (no son las normas TCSA maestras). Version + SHA + preimagen + CAS."""
from __future__ import annotations
import re
from pathlib import Path
from . import config
from .storage import atomic_write, journal, sha_bytes, sha_file, utc

FILE = "NORMAS-TCSA3000.md"
VER = re.compile(r"^Version:\s*(\d+)\s*$", re.M)

def path() -> Path:
    return config.home() / FILE

def leer() -> dict:
    p = path(); t = p.read_text("utf-8")
    m = VER.search(t)
    return {"archivo": str(p), "version": int(m.group(1)) if m else 0, "sha256": sha_file(p), "texto": t}

def actualizar(texto: str, sha_esperado: str, actor: str) -> dict:
    if not actor or not texto.strip() or len(texto) > 200_000:
        raise ValueError("NORMAS_ACTUALIZACION_INVALIDA")
    cur = leer()
    if cur["sha256"] != sha_esperado:
        raise ValueError("NORMAS_CAMBIARON_RELEER (CAS)")
    pre = config.home() / "VERSIONES" / "normas" / ("NORMAS-v%d-%s.md" % (cur["version"], cur["sha256"][:12]))
    if not pre.exists():
        atomic_write(pre, path().read_bytes())
    new_v = cur["version"] + 1
    texto = VER.sub("Version: %d" % new_v, texto, count=1) if VER.search(texto) else "Version: %d\n" % new_v + texto
    data = texto.encode("utf-8"); atomic_write(path(), data)
    journal(config.data_dir() / "normas.journal.jsonl", "NORMAS_ACTUALIZADAS",
            {"de": cur["version"], "a": new_v, "shaAnterior": cur["sha256"], "shaNuevo": sha_bytes(data), "preimagen": str(pre), "actor": actor})
    return {"version": new_v, "sha256": sha_bytes(data), "preimagen": str(pre), "at": utc()}

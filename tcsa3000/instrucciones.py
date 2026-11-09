"""Registro de INSTRUCCIONES DE PROYECTO (los textos que se pegan en ChatGPT/Claude/otros) con versiones, fechas y nombres
entendibles. Regla de nombres: "<PROYECTO> - <Nombre claro> - v<N> (<AAAA-MM-DD>).txt" en 01-INSTRUCCIONES/.
Una sola version VIGENTE por proyecto y clave; las anteriores quedan SUSTITUIDAS (nunca se borran)."""
from __future__ import annotations
import json, re
from pathlib import Path
from . import continuidad as C
from .storage import sha_bytes, utc

REG = "01-INSTRUCCIONES/REGISTRO-INSTRUCCIONES.json"
CLAVE = re.compile(r"[a-z0-9][a-z0-9-]{1,39}\Z")
SEMILLA = [  # ficheros historicos ya existentes (no se renombran: se registran tal cual)
    ("TCSA", "instrucciones-proyecto", "Instrucciones de proyecto TCSA", 1, "2026-11-09", "01-INSTRUCCIONES/COPIAR-INSTRUCCIONES-PROYECTO-R1.txt"),
    ("TCSA", "arranque", "Arranque TCSA (ChatGPT y Claude)", 2, "2026-11-09", "01-INSTRUCCIONES/BOOTSTRAP-CHATGPT-CLAUDE-R2.txt"),
    ("TCSA", "arranque", "Arranque TCSA (ChatGPT y Claude)", 3, "2026-11-09", "01-INSTRUCCIONES/BOOTSTRAP-CHATGPT-CLAUDE-R3.txt"),
    ("TCSA", "arranque", "Arranque TCSA (ChatGPT y Claude)", 4, "2026-11-09", "01-INSTRUCCIONES/BOOTSTRAP-CHATGPT-CLAUDE-R4.txt"),
    ("TCSA", "arranque", "Arranque ligero TCSA (ChatGPT y Claude)", 5, "2026-11-09", "01-INSTRUCCIONES/BOOTSTRAP-CHATGPT-CLAUDE-R5.txt"),
    ("TCSA", "arranque", "Arranque TCSA3000 corto (cualquier IA)", 6, "2026-11-09", "01-INSTRUCCIONES/BOOTSTRAP-CHATGPT-CLAUDE-R6.txt"),
]

def _p(cfg) -> Path:
    return C.root(cfg) / REG

def _cargar(cfg) -> dict:
    p = _p(cfg)
    if p.is_file():
        return C._read_json(p)
    r = C.root(cfg); items = []
    for proy, clave, nombre, v, fecha, arch in SEMILLA:
        if (r / arch).is_file():
            items.append({"id": "%s-%s-v%d" % (proy, clave, v), "proyecto": proy, "clave": clave, "nombre": nombre, "version": v, "fecha": fecha,
                          "archivo": arch, "estado": "SUSTITUIDA", "sha256": sha_bytes((r / arch).read_bytes()), "origen": "historico registrado"})
    for clave in {i["clave"] for i in items}:  # la mas alta de cada clave queda vigente
        top = max((i for i in items if i["clave"] == clave), key=lambda i: i["version"]); top["estado"] = "VIGENTE"
    return {"schema": "tcsa.instrucciones.v1", "regla": "Nombre: <PROYECTO> - <Nombre claro> - v<N> (<AAAA-MM-DD>).txt; una VIGENTE por proyecto y clave.",
            "instrucciones": items}

def listar(cfg, proyecto: str = "") -> dict:
    d = _cargar(cfg); it = [i for i in d["instrucciones"] if not proyecto or i["proyecto"] == proyecto]
    it.sort(key=lambda i: (i["proyecto"], i["clave"], -i["version"]))
    return {"regla": d["regla"], "instrucciones": it}

def leer(cfg, iid: str) -> dict:
    i = next((x for x in _cargar(cfg)["instrucciones"] if x["id"] == iid), None)
    if not i: raise LookupError("INSTRUCCION_NO_EXISTE:" + iid)
    return dict(i, texto=(C.root(cfg) / i["archivo"]).read_text("utf-8-sig", errors="replace"))

def vigente(proyecto: str, clave: str, cfg=None):
    from . import config
    cfg = cfg or config.load()
    i = next((x for x in _cargar(cfg)["instrucciones"] if x["proyecto"] == proyecto and x["clave"] == clave and x["estado"] == "VIGENTE"), None)
    return leer(cfg, i["id"]) if i else None

def nueva_version(cfg, proyecto: str, clave: str, nombre: str, texto: str, notas: str = "", agente: str = "") -> dict:
    if not C.PID.fullmatch(proyecto or "") and proyecto != "TCSA": raise ValueError("PROYECTO_INVALIDO")
    if not CLAVE.fullmatch(clave or ""): raise ValueError("CLAVE_INVALIDA (minusculas y guiones, p.ej. arranque)")
    if len((nombre or "").strip()) < 4 or len((texto or "").strip()) < 20: raise ValueError("FALTAN_NOMBRE_O_TEXTO")
    r = C.root(cfg); p = _p(cfg); op = C._op_id(proyecto if C.PID.fullmatch(proyecto) else "TCSA-CORE", "INSTR")
    with C._lock(str(p)):
        old = p.read_bytes() if p.is_file() else None
        d = _cargar(cfg); prev = [i for i in d["instrucciones"] if i["proyecto"] == proyecto and i["clave"] == clave]
        v = max([i["version"] for i in prev] or [0]) + 1; fecha = utc()[:10]
        limpio = re.sub(r'[\\\\/:*?"<>|]', "-", nombre.strip())[:80]
        arch = "01-INSTRUCCIONES/%s - %s - v%d (%s).txt" % (proyecto, limpio, v, fecha)
        b = texto.strip().encode("utf-8") + b"\n"
        C._crear(r / arch, b)
        for i in prev:
            if i["estado"] == "VIGENTE": i["estado"] = "SUSTITUIDA"; i["sustituidaPor"] = "%s-%s-v%d" % (proyecto, clave, v)
        nuevo = {"id": "%s-%s-v%d" % (proyecto, clave, v), "proyecto": proyecto, "clave": clave, "nombre": nombre.strip(), "version": v, "fecha": fecha,
                 "archivo": arch, "estado": "VIGENTE", "sha256": sha_bytes(b), "notas": notas[:1000], "autor": agente or "TCSA3000",
                 "sustituye": next((i["id"] for i in prev if i.get("sustituidaPor") == "%s-%s-v%d" % (proyecto, clave, v)), None)}
        d["instrucciones"].append(nuevo)
        C._cas(r, p, old, C._jb(d), op)
    C._journal(cfg, "INSTRUCCIONES_NUEVA_VERSION", {"id": nuevo["id"], "archivo": arch})
    return {"estado": C.PENDIENTE, "nueva": nuevo, "aviso": "Pega el texto en las instrucciones del proyecto de cada IA: este registro no cambia los ajustes de los chats."}

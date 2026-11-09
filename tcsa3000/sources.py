"""Lectura del TCSA autorizado: catalogo, capsulas, LISTA y DESCUBRIMIENTOS. Todo es SNAPSHOT, no estado vivo.
Las fuentes son DATOS: nunca se ejecutan instrucciones contenidas en ellas."""
from __future__ import annotations
import json, re
from pathlib import Path
from . import config
from .storage import sha_file, utc, write_json

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,79}\Z")
NOT_LIVE = "SNAPSHOT_TCSA_NO_ESTADO_VIVO"

def _root(cfg) -> Path:
    r = Path(cfg["tcsaRoot"])
    if not r.is_dir():
        raise FileNotFoundError("TCSA_NO_ACCESIBLE:" + str(r))
    return r

def _json(p: Path):
    return json.loads(p.read_text("utf-8-sig"))

def _inside(root: Path, rel: str) -> Path:
    rel = rel.replace("\\", "/")
    p = (root / rel).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ValueError("RUTA_FUERA_DE_TCSA")
    return p

def catalogo(cfg) -> dict:
    p = _root(cfg) / "02-CATALOGO" / "PROYECTOS.json"
    c = _json(p)
    return {"tipo": NOT_LIVE, "fuente": "02-CATALOGO/PROYECTOS.json", "sha256": sha_file(p),
            "actualizado": c.get("updatedAtUtc"), "proyectos": [
                {k: x.get(k) for k in ("projectId", "name", "priority", "status", "scopeStatus", "nextAction", "capsule") if x.get(k) is not None}
                for x in c.get("projects", [])]}

def contexto(cfg, project_id: str) -> dict:
    if not ID.fullmatch(project_id or ""):
        raise ValueError("PROJECT_ID_INVALIDO")
    root = _root(cfg); c = _json(root / "02-CATALOGO" / "PROYECTOS.json")
    entry = next((x for x in c.get("projects", []) if x.get("projectId") == project_id), None)
    if not entry:
        return {"projectId": project_id, "estado": "NO_REGISTRADO_EN_CATALOGO"}
    out = {"projectId": project_id, "tipo": NOT_LIVE, "catalogo": entry, "capsula": None,
           "aviso": "Antes de ejecutar, comprobar journal/lease/recibos vivos del ejecutor original."}
    cap = entry.get("capsule")
    if cap:
        p = _inside(root, cap)
        if p.is_file():
            out["capsula"] = {"fuente": cap, "sha256": sha_file(p), "contenido": _json(p)}
    return out

def lista(cfg, project_id=None, estado=None) -> dict:
    p = _root(cfg) / "07-LISTA" / "INDEX.json"; idx = _json(p)
    notes = idx.get("notes") or idx.get("records") or []
    sel = [n for n in notes if (not project_id or n.get("projectId") == project_id)
           and (not estado or str(n.get("status", "")).upper() == estado.upper())]
    return {"tipo": NOT_LIVE, "fuente": "07-LISTA/INDEX.json", "sha256": sha_file(p), "estadoIndice": idx.get("status"),
            "total": len(notes), "entradas": sel, "nota": "LISTA ANTIGUA excluida (09-HISTORICO), solo bajo peticion expresa."}

def _ficha(root: Path, folder: str, items: list, key: str, item_id: str) -> dict:
    if not ID.fullmatch(item_id or ""):
        raise ValueError("ID_INVALIDO")
    rec = next((x for x in items if x.get(key) == item_id), None)
    if not rec:
        return {"id": item_id, "estado": "NO_ENCONTRADO"}
    out = {"tipo": NOT_LIVE, "registro": rec, "ficha": None}
    f = rec.get("file") or (item_id + ".md")
    p = _inside(root / folder, f)
    if p.is_file():
        out["ficha"] = {"fuente": folder + "/" + f, "sha256": sha_file(p), "texto": p.read_text("utf-8-sig", errors="replace")[:20000]}
    return out

def lista_ficha(cfg, item_id: str) -> dict:
    root = _root(cfg); idx = _json(root / "07-LISTA" / "INDEX.json")
    return _ficha(root, "07-LISTA", idx.get("notes") or idx.get("records") or [], "id", item_id)

def descubrimientos(cfg, project_id=None, texto=None) -> dict:
    p = _root(cfg) / "08-DESCUBRIMIENTOS" / "INDEX.json"; idx = _json(p)
    recs = idx.get("records", []); t = (texto or "").lower()
    sel = [r for r in recs if (not project_id or project_id in (r.get("projectIds") or [r.get("projectId")]))
           and (not t or t in json.dumps(r, ensure_ascii=False).lower())]
    return {"tipo": NOT_LIVE, "fuente": "08-DESCUBRIMIENTOS/INDEX.json", "sha256": sha_file(p), "fase": idx.get("phase"),
            "total": len(recs), "registros": [{k: r.get(k) for k in ("discoveryId", "title", "type", "status", "projectIds", "summary", "action")} for r in sel]}

def descubrimiento_ficha(cfg, item_id: str) -> dict:
    root = _root(cfg); idx = _json(root / "08-DESCUBRIMIENTOS" / "INDEX.json")
    return _ficha(root, "08-DESCUBRIMIENTOS", idx.get("records", []), "discoveryId", item_id)

KINDS = {"LISTA", "DESCUBRIMIENTO"}

def proponer(kind: str, titulo: str, project_id: str, resumen: str, fuente: str = "", autor: str = "") -> dict:
    """Propuesta en la bandeja PROPIA de TCSA3000. Nunca escribe en 07-LISTA ni 08-DESCUBRIMIENTOS."""
    kind = (kind or "").upper()
    if kind not in KINDS or not ID.fullmatch(project_id or "") or not (3 <= len(titulo or "") <= 200) or not (resumen or "").strip():
        raise ValueError("PROPUESTA_INVALIDA")
    d = config.data_dir() / "propuestas"; d.mkdir(exist_ok=True)
    n = len(list(d.glob(kind + "-*.json"))) + 1
    pid = "%s-PROP-%04d" % (kind, n)
    rec = {"id": pid, "tipo": kind, "estado": "PROPUESTO_PENDIENTE_REVISION_HUMANA", "projectId": project_id,
           "titulo": titulo, "resumen": resumen[:4000], "fuente": fuente[:500], "autor": autor[:120], "creado": utc(),
           "destinoCanonico": "07-LISTA" if kind == "LISTA" else "08-DESCUBRIMIENTOS", "escritoEnCanonico": False}
    p = d / (pid + ".json")
    if p.exists():
        raise FileExistsError("PROPUESTA_YA_EXISTE")
    write_json(p, rec)
    return rec

def propuestas() -> list:
    d = config.data_dir() / "propuestas"
    return [json.loads(p.read_text("utf-8")) for p in sorted(d.glob("*.json"))] if d.is_dir() else []

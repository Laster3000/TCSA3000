"""Propuestas de trabajo (maestro v1.5.0, seccion 19: trabajo por propuesta y bloque unico).

Ciclo: PROPUESTA -> ACEPTADA -> EN_EJECUCION -> TERMINADA | BLOQUEADA (| DESCARTADA).
La aceptacion del usuario cubre TODO lo listado (pasos y efectos): se ejecuta en
un solo bloque sin microconfirmaciones. Solo se para por un efecto NO listado
irreversible/protegido, un bloqueo que solo resuelve el usuario o riesgo de
perdida de datos; esa parada queda anotada aqui.
Se guardan en TCSA/11-PROPUESTAS (continuidad canonica, espejada a Drive).
Distinto de 'tcsa3000_proponer' (bandeja de LISTA/DESCUBRIMIENTOS para revision).
"""
from __future__ import annotations
import json
import re
from . import continuidad as C
from .storage import utc, write_json

ESTADOS = ("PROPUESTA", "ACEPTADA", "EN_EJECUCION", "TERMINADA", "BLOQUEADA", "DESCARTADA")
PASOS_OK = {"PROPUESTA": {"ACEPTADA", "DESCARTADA"}, "ACEPTADA": {"EN_EJECUCION", "BLOQUEADA", "DESCARTADA"},
            "EN_EJECUCION": {"TERMINADA", "BLOQUEADA"}, "BLOQUEADA": {"EN_EJECUCION", "DESCARTADA"},
            "TERMINADA": set(), "DESCARTADA": set()}
ID = re.compile(r"PROP-\d{3,5}\Z")


def _dir(cfg):
    d = C.root(cfg) / "11-PROPUESTAS"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _lista_txt(v):
    if isinstance(v, str):
        v = [x.strip() for x in v.splitlines() if x.strip()]
    return [str(x)[:500] for x in (v or [])][:60]


def _md(rec):
    l = [f"# {rec['id']} - {rec['titulo']}", "",
         f"Proyecto: {rec['projectId']} | Estado: {rec['estado']} | Creada: {rec['creada']} | Autor: {rec.get('autor', '')}", "",
         "## Objetivo", rec["objetivo"], "", "## Pasos (cubiertos por la aceptacion)"]
    l += [f"{i + 1}. {p}" for i, p in enumerate(rec["pasos"])] or ["-"]
    l += ["", "## Efectos (descargas, instalaciones, cambios protegidos)"] + ([f"- {e}" for e in rec["efectos"]] or ["- ninguno"])
    l += ["", "## Riesgos", rec.get("riesgos") or "-", "", "## Criterios de aceptacion y pruebas", rec.get("criterios") or "-", "", "## Historial"]
    l += [f"- {h['at']} {h['estado']} ({h.get('quien', '')}): {h.get('nota', '')}" for h in rec["historial"]]
    return "\n".join(l) + "\n"


def _guardar(cfg, rec):
    d = _dir(cfg)
    write_json(d / f"{rec['id']}.json", rec)
    (d / f"{rec['id']}.md").write_text(_md(rec), encoding="utf-8")
    idx = sorted([{k: r.get(k) for k in ("id", "titulo", "projectId", "estado", "creada", "actualizada", "listaId")}
                  for r in _todas(cfg)], key=lambda r: r["id"])
    write_json(d / "INDEX.json", {"schema": "tcsa.propuestas.v1", "actualizado": utc(), "propuestas": idx})


def _todas(cfg):
    return [json.loads(p.read_text("utf-8")) for p in sorted(_dir(cfg).glob("PROP-*.json"))]


def crear(cfg, project_id, titulo, objetivo, pasos=None, efectos=None, riesgos="", criterios="", agente="", lista_id="", pid_forzado=""):
    if not C.PID.fullmatch(project_id or ""):
        raise ValueError("PROJECT_ID_INVALIDO")
    if not (3 <= len(titulo or "") <= 200) or not (objetivo or "").strip():
        raise ValueError("PROPUESTA_INVALIDA: titulo (3-200) y objetivo obligatorios")
    existentes = _todas(cfg)
    if pid_forzado:
        if not ID.fullmatch(pid_forzado) or any(r["id"] == pid_forzado for r in existentes):
            raise ValueError("ID_PROPUESTA_INVALIDO_O_EXISTENTE")
        pid = pid_forzado
    else:
        n = max([int(r["id"].split("-")[1]) for r in existentes] or [0]) + 1
        pid = "PROP-%03d" % n
    rec = {"schema": "tcsa.propuesta.v1", "id": pid, "projectId": project_id, "titulo": titulo.strip(),
           "objetivo": objetivo.strip()[:6000], "pasos": _lista_txt(pasos), "efectos": _lista_txt(efectos),
           "riesgos": (riesgos or "")[:3000], "criterios": (criterios or "")[:3000], "autor": (agente or "")[:120],
           "listaId": lista_id or None, "estado": "PROPUESTA", "creada": utc(), "actualizada": utc(),
           "historial": [{"at": utc(), "estado": "PROPUESTA", "quien": agente or "", "nota": "creada"}]}
    _guardar(cfg, rec)
    C._journal(cfg, "PROPUESTA_CREAR", {"id": pid, "projectId": project_id})
    return rec


def ver(cfg, pid):
    p = _dir(cfg) / f"{pid}.json"
    if not ID.fullmatch(pid or "") or not p.is_file():
        raise ValueError("PROPUESTA_NO_EXISTE")
    return json.loads(p.read_text("utf-8"))


def lista(cfg, project_id="", estado=""):
    return {"tipo": "SNAPSHOT_TCSA_NO_ESTADO_VIVO", "fuente": "11-PROPUESTAS/INDEX.json",
            "norma": "Aceptar una propuesta autoriza todos sus pasos y efectos listados; se ejecuta en un solo bloque.",
            "propuestas": [{k: r.get(k) for k in ("id", "titulo", "projectId", "estado", "creada", "actualizada", "listaId")}
                           for r in _todas(cfg) if (not project_id or r["projectId"] == project_id) and (not estado or r["estado"] == estado)]}


def cambiar(cfg, pid, estado, nota="", quien="", evidencias=None, closure_id=""):
    estado = (estado or "").upper()
    if estado not in ESTADOS:
        raise ValueError("ESTADO_INVALIDO: " + ", ".join(ESTADOS))
    rec = ver(cfg, pid)
    if estado not in PASOS_OK[rec["estado"]]:
        raise ValueError(f"TRANSICION_NO_PERMITIDA: {rec['estado']} -> {estado}")
    if estado == "ACEPTADA" and not (quien or "").strip():
        raise ValueError("FALTA_QUIEN_ACEPTA")
    if estado == "TERMINADA" and not evidencias:
        raise ValueError("TERMINADA_SIN_EVIDENCIAS: nada se da por terminado sin prueba real")
    if estado == "BLOQUEADA" and not (nota or "").strip():
        raise ValueError("FALTA_MOTIVO_DEL_BLOQUEO")
    h = {"at": utc(), "estado": estado, "quien": (quien or "")[:120], "nota": (nota or "")[:2000]}
    if evidencias:
        h["evidencias"] = _lista_txt(evidencias)
    if closure_id:
        h["closureId"] = closure_id[:120]
    rec["historial"].append(h)
    rec["estado"], rec["actualizada"] = estado, utc()
    if estado == "ACEPTADA":
        rec["aceptacion"] = {"at": utc(), "quien": quien, "cubre": {"pasos": len(rec["pasos"]), "efectos": rec["efectos"]}}
    _guardar(cfg, rec)
    C._journal(cfg, "PROPUESTA_" + estado, {"id": pid, "quien": quien})
    return rec

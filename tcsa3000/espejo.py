"""Respaldo en Drive como ESPEJO de la continuidad canonica local (TCSA3000/TCSA).
- Local -> Drive: copia lo nuevo o cambiado. Nunca borra nada en Drive.
- Drive -> local: importa SOLO ficheros nuevos creados en Drive (p.ej. cierres de una IA web sin MCP).
- Conflicto (cambiado en los dos lados desde el ultimo espejo): gana local; la version de Drive se conserva en
  TCSA/99-RECUPERACION/TCSA3000/CONFLICTOS-DRIVE/<fecha>/<ruta>.
- Cache por tamano+fecha para no releer Drive entero en cada ciclo."""
from __future__ import annotations
import json, os, shutil
from pathlib import Path
from . import config
from .storage import sha_file, utc, write_json

IGNORAR = (".tcsa3000-stage", ".tmp-", "desktop.ini", ".~lock", "Thumbs.db")

def _manifest_path() -> Path:
    return config.data_dir() / "respaldo-manifiesto.json"

def _cargar() -> dict:
    p = _manifest_path()
    return json.loads(p.read_text("utf-8")) if p.exists() else {"ficheros": {}}

def _listar(root: Path) -> dict:
    out = {}
    if not root.is_dir():
        return out
    for dp, dn, fn in os.walk(root):
        for f in fn:
            if any(x in f for x in IGNORAR):
                continue
            p = Path(dp) / f; st = p.stat()
            out[p.relative_to(root).as_posix()] = (st.st_size, st.st_mtime_ns)
    return out

def _copiar(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".tmp-tcsa3000")
    shutil.copy2(src, tmp); os.replace(tmp, dst)

def _sha_cache(path: Path, meta: tuple, prev: dict | None, lado: str) -> str:
    if prev and prev.get(lado + "Meta") == list(meta):
        return prev["sha256"] if lado == "local" else prev.get("remotoSha256", prev["sha256"])
    return sha_file(path)

def sincronizar(cfg: dict, importar_todo: bool = False) -> dict:
    local, remoto = Path(cfg["tcsaRoot"]), Path(cfg["respaldoDir"])
    if not remoto.parent.exists():
        return {"estado": "BLOQUEADO", "motivo": "UNIDAD_DE_RESPALDO_NO_ACCESIBLE:" + str(remoto.parent)}
    local.mkdir(parents=True, exist_ok=True); remoto.mkdir(parents=True, exist_ok=True)
    man = _cargar(); prev_all = man["ficheros"]; nuevo = {}
    L, R = _listar(local), _listar(remoto)
    subidos, importados, conflictos, iguales, errores = [], [], [], 0, []
    ts = utc().replace(":", "").replace("-", "")[:15]
    for rel in sorted(set(L) | set(R)):
        prev = prev_all.get(rel)
        try:
            lp, rp = local / rel, remoto / rel
            if rel in L:
                ls = _sha_cache(lp, L[rel], prev, "local")
                if rel in R:
                    rs = _sha_cache(rp, R[rel], prev, "remoto")
                    if ls != rs:
                        cambio_remoto = prev is not None and rs != prev.get("remotoSha256", prev["sha256"])
                        cambio_local = prev is None or ls != prev["sha256"]
                        if cambio_remoto and not cambio_local:
                            # solo cambio en Drive: se trae (p.ej. edicion hecha por otra IA en el respaldo), preservando la local
                            _copiar(lp, local / "99-RECUPERACION" / "TCSA3000" / "PREVIO-A-IMPORTAR" / ts / rel)
                            _copiar(rp, lp); importados.append(rel); ls = rs
                        else:
                            if cambio_remoto:
                                _copiar(rp, local / "99-RECUPERACION" / "TCSA3000" / "CONFLICTOS-DRIVE" / ts / rel); conflictos.append(rel)
                            _copiar(lp, rp); subidos.append(rel); rs = ls
                    else:
                        iguales += 1
                else:
                    _copiar(lp, rp); subidos.append(rel); rs = ls
                nuevo[rel] = {"sha256": ls, "remotoSha256": ls, "localMeta": [lp.stat().st_size, lp.stat().st_mtime_ns],
                              "remotoMeta": [rp.stat().st_size, rp.stat().st_mtime_ns]}
            else:  # solo en Drive
                if prev is not None and not importar_todo:
                    nuevo[rel] = prev; continue  # se borro en local a proposito: el respaldo lo conserva, no se reimporta
                _copiar(rp, lp); importados.append(rel); s = sha_file(lp)
                nuevo[rel] = {"sha256": s, "remotoSha256": s, "localMeta": [lp.stat().st_size, lp.stat().st_mtime_ns], "remotoMeta": list(R[rel])}
        except OSError as e:
            errores.append({"ruta": rel, "error": str(e)})
            if prev: nuevo[rel] = prev
    write_json(_manifest_path(), {"actualizado": utc(), "local": str(local), "respaldo": str(remoto), "ficheros": nuevo})
    res = {"estado": "OK" if not errores else "PARCIAL", "at": utc(), "local": str(local), "respaldo": str(remoto), "ficheros": len(nuevo),
           "subidosADrive": len(subidos), "importadosDeDrive": len(importados), "conflictos": conflictos[:50], "iguales": iguales,
           "errores": errores[:20], "detalle": {"subidos": subidos[:50], "importados": importados[:50]},
           "nota": "Escrito en la carpeta sincronizada de Drive: la nube lo recibe al sincronizar (confirmable con tcsa3000_confirmar_sync)."}
    return res

def verificar(cfg: dict) -> dict:
    """Comparacion completa por SHA-256 (sin cache) entre local y respaldo."""
    local, remoto = Path(cfg["tcsaRoot"]), Path(cfg["respaldoDir"])
    L, R = _listar(local), _listar(remoto)
    solo_l = sorted(set(L) - set(R)); solo_r = sorted(set(R) - set(L)); dif = []
    for rel in sorted(set(L) & set(R)):
        if L[rel][0] != R[rel][0] or sha_file(local / rel) != sha_file(remoto / rel):
            dif.append(rel)
    return {"local": len(L), "respaldo": len(R), "soloLocal": solo_l[:100], "soloRespaldo": solo_r[:100], "distintos": dif[:100],
            "identicos": len(set(L) & set(R)) - len(dif)}

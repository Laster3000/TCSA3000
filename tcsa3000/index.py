"""Indice FTS5 por allowlist con citas exactas (archivo, lineas, SHA). Indice != estado vivo."""
from __future__ import annotations
import json, re, sqlite3
from pathlib import Path
from . import config
from .storage import sha_bytes

ALLOWED = {".md", ".txt", ".json"}
MAX_BYTES = 2 * 1024 * 1024
WINDOW, STEP = 30, 20
PID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{1,79}\Z")

def db_path() -> Path:
    return config.data_dir() / "indice.sqlite3"

def connect(path: Path | None = None):
    db = sqlite3.connect(path or db_path())
    db.execute("""CREATE TABLE IF NOT EXISTS docs(id INTEGER PRIMARY KEY, project_id TEXT, rel TEXT,
                  root TEXT, sha TEXT, indexed_at TEXT, UNIQUE(project_id, root, rel))""")
    db.execute("""CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, doc_id INTEGER, line_from INTEGER, line_to INTEGER)""")
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(title, body, tokenize='unicode61 remove_diacritics 2')")
    return db

def _safe(root: Path, rel: str) -> Path:
    r = Path(rel)
    if r.is_absolute() or not r.parts or ".." in r.parts:
        raise ValueError("RUTA_INSEGURA:" + rel)
    f = (root / r).resolve(strict=True)
    if not f.is_file() or f.is_symlink() or not f.is_relative_to(root.resolve(strict=True)):
        raise ValueError("FUENTE_NO_VALIDA:" + rel)
    if f.suffix.lower() not in ALLOWED or f.stat().st_size > MAX_BYTES:
        raise ValueError("TIPO_O_TAMANO_NO_PERMITIDO:" + rel)
    return f

def add(db, root: Path, rel: str, project_id: str) -> dict:
    if not PID.fullmatch(project_id):
        raise ValueError("PROJECT_ID_INVALIDO")
    f = _safe(root, rel); raw = f.read_bytes(); sha = sha_bytes(raw)
    text = raw.decode("utf-8-sig", errors="replace")
    key = (project_id, str(root.resolve()), Path(rel).as_posix())
    old = db.execute("SELECT id, sha FROM docs WHERE project_id=? AND root=? AND rel=?", key).fetchone()
    if old and old[1] == sha:
        return {"status": "SIN_CAMBIOS", "path": key[2], "sha256": sha}
    from .storage import utc
    with db:
        if old:
            for (cid,) in db.execute("SELECT id FROM chunks WHERE doc_id=?", (old[0],)).fetchall():
                db.execute("DELETE FROM fts WHERE rowid=?", (cid,))
            db.execute("DELETE FROM chunks WHERE doc_id=?", (old[0],))
            db.execute("DELETE FROM docs WHERE id=?", (old[0],))
        doc = db.execute("INSERT INTO docs(project_id, rel, root, sha, indexed_at) VALUES(?,?,?,?,?)", (project_id, key[2], key[1], sha, utc())).lastrowid
        lines = text.splitlines() or [""]
        for start in range(0, len(lines), STEP):
            part = lines[start:start + WINDOW]
            cid = db.execute("INSERT INTO chunks(doc_id, line_from, line_to) VALUES(?,?,?)", (doc, start + 1, start + len(part))).lastrowid
            db.execute("INSERT INTO fts(rowid, title, body) VALUES(?,?,?)", (cid, Path(rel).name, "\n".join(part)))
            if start + WINDOW >= len(lines):
                break
    return {"status": "INDEXADO", "path": key[2], "sha256": sha, "lineas": len(lines)}

def _query(text: str, mode: str) -> str:
    words = [w for w in re.findall(r"[\w\-\.]+", text, re.UNICODE) if len(w) > 1][:12]
    if not words:
        raise ValueError("CONSULTA_VACIA")
    return (" %s " % mode).join('"%s"' % w.replace('"', "") for w in words)

def search(db, text: str, project_id: str | None = None, limit: int = 8) -> dict:
    if len(text) > 300 or not 1 <= limit <= 30:
        raise ValueError("CONSULTA_INVALIDA")
    if project_id and not PID.fullmatch(project_id):
        raise ValueError("PROJECT_ID_INVALIDO")
    for mode in ("AND", "OR"):
        q = _query(text, mode)
        sql = """SELECT d.project_id, d.rel, d.sha, c.line_from, c.line_to, snippet(fts,1,'[',']',' ... ',16)
                 FROM fts JOIN chunks c ON c.id=fts.rowid JOIN docs d ON d.id=c.doc_id
                 WHERE fts MATCH ? """ + ("AND d.project_id=? " if project_id else "") + "ORDER BY bm25(fts) LIMIT ?"
        args = (q, project_id, limit) if project_id else (q, limit)
        rows = db.execute(sql, args).fetchall()
        if rows:
            break
    return {"modo": mode if rows else "SIN_RESULTADOS", "resultados": [
        {"projectId": r[0], "fuente": r[1], "sha256": r[2], "lineas": [r[3], r[4]], "extracto": r[5],
         "cita": "%s#L%d-L%d" % (r[1], r[3], r[4]), "tipo": "INDICE_LOCAL_NO_ESTADO_VIVO"} for r in rows]}

def _items(cfg: dict, root: Path) -> list:
    """Allowlist configurada + automatico: protocolos TCSA, capsulas del catalogo y fichas de LISTA/DESCUBRIMIENTOS."""
    from .continuidad import DOCUMENTOS
    items, seen = [], set()
    def put(pid, rel):
        if rel not in seen:
            seen.add(rel); items.append({"projectId": pid, "path": rel})
    for it in cfg["allowlist"]:
        put(it["projectId"], it["path"])
    for rel in DOCUMENTOS.values():
        if rel.endswith((".md", ".txt", ".json")):
            put("TCSA-CORE", rel)
    try:
        cat = json.loads((root / "02-CATALOGO" / "PROYECTOS.json").read_text("utf-8-sig"))
        for x in cat.get("projects", []):
            if x.get("capsule") and PID.fullmatch(x.get("projectId", "")):
                put(x["projectId"], x["capsule"])
    except (OSError, ValueError):
        pass
    for folder in ("07-LISTA", "08-DESCUBRIMIENTOS"):
        d = root / folder
        if d.is_dir():
            for f in sorted(d.glob("*.md"))[:500]:
                put("TCSA-CORE", folder + "/" + f.name)
    return items

def reindex(cfg: dict) -> dict:
    root = Path(cfg["tcsaRoot"]); out = []
    db = connect()
    try:
        for item in _items(cfg, root):
            try:
                out.append(add(db, root, item["path"], item["projectId"]))
            except (ValueError, OSError) as e:
                out.append({"status": "OMITIDO", "path": item.get("path"), "motivo": str(e)})
    finally:
        db.close()
    return {"raiz": str(root), "resultados": out}

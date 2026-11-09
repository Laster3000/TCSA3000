#!/usr/bin/env python3
"""TCSA3000 F0/F1 prototype: deterministic, explicit-scope, local SQLite FTS5 search.

No autonomous execution, online traffic, model calls, Drive writes or live status claims.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

MAX_DOCUMENT_BYTES = 1024 * 1024
ALLOWED_SUFFIXES = {".md", ".txt", ".json"}
IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{1,79}\Z")


def open_db(workspace: Path):
    data = workspace.resolve(strict=True) / "data"
    data.mkdir(exist_ok=True)
    db = sqlite3.connect(data / "tcsa3000-fts.sqlite3")
    db.execute("""CREATE TABLE IF NOT EXISTS documents(
         id INTEGER PRIMARY KEY, project_id TEXT NOT NULL,
         source_root TEXT NOT NULL, relative_path TEXT NOT NULL,
         sha256 TEXT NOT NULL, UNIQUE(project_id,source_root,relative_path))""")
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(title,body, tokenize='unicode61')")
    return db


def add_document(db: sqlite3.Connection, source_root: Path, relpath: str, project_id: str):
    if not IDENT.fullmatch(project_id):
        raise ValueError("INVALID_PROJECT_ID")
    rel = Path(relpath)
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise ValueError("UNSAFE_RELATIVE_PATH")
    root = source_root.resolve(strict=True)
    file = (root / rel).resolve(strict=True)
    if not file.is_file() or file.is_symlink() or not file.is_relative_to(root):
        raise ValueError("SOURCE_MISSING_OR_UNSAFE")
    if file.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError("UNSUPPORTED_SOURCE_EXTENSION")
    size = file.stat().st_size
    if size > MAX_DOCUMENT_BYTES:
        raise ValueError("SOURCE_TOO_LARGE")
    raw = file.read_bytes()
    body = raw.decode("utf-8-sig", errors="strict")
    digest = hashlib.sha256(raw).hexdigest()
    key = (project_id, str(root), rel.as_posix())
    prior = db.execute(
        "SELECT id,sha256 FROM documents WHERE project_id=? AND source_root=? AND relative_path=?",
        key).fetchone()
    if prior and prior[1] == digest:
        return {"status": "UNCHANGED", "sha256": digest, "source": rel.as_posix()}
    with db:
        if prior:
            db.execute("DELETE FROM fts WHERE rowid=?", (prior[0],))
            db.execute("DELETE FROM documents WHERE id=?", (prior[0],))
        cursor = db.execute("""INSERT INTO documents(project_id,source_root,relative_path,sha256)
                            VALUES(?,?,?,?)""", key + (digest,))
        db.execute("INSERT INTO fts(rowid,title,body) VALUES(?,?,?)",
                   (cursor.lastrowid, rel.name, body))
    return {"status": "INDEXED", "sha256": digest, "source": rel.as_posix()}


def find(db: sqlite3.Connection, project_id: str, words: str, limit: int = 10):
    if not IDENT.fullmatch(project_id):
        raise ValueError("INVALID_PROJECT_ID")
    if not words or len(words) > 250 or not 1 <= limit <= 50:
        raise ValueError("INVALID_QUERY")
    try:
        records = db.execute("""SELECT documents.relative_path, documents.sha256,
                                   snippet(fts,1,'[',']',' ... ',18) AS excerpt
                 FROM fts JOIN documents ON fts.rowid=documents.id
                 WHERE fts MATCH ? AND documents.project_id=?
                 ORDER BY bm25(fts) LIMIT ?""",
                             (words, project_id, limit)).fetchall()
    except sqlite3.OperationalError as e:
        raise ValueError("INVALID_FTS_QUERY") from e
    return [{"path": r[0], "sha256": r[1], "excerpt": r[2],
             "projectId": project_id, "sourceType": "LOCAL_INDEX_NOT_LIVE_STATE"} for r in records]


def main():
    p = argparse.ArgumentParser(description="TCSA3000 scoped local FTS5 prototype")
    p.add_argument("--workspace", type=Path, required=True)
    subs = p.add_subparsers(dest="command", required=True)
    subs.add_parser("doctor")
    i = subs.add_parser("index")
    i.add_argument("--source-root", type=Path, required=True)
    i.add_argument("--project-id", required=True)
    i.add_argument("--file", action="append", required=True)
    s = subs.add_parser("search")
    s.add_argument("--project-id", required=True)
    s.add_argument("--query", required=True)
    args = p.parse_args()
    try:
        db = open_db(args.workspace)
        if args.command == "doctor":
            db.execute("SELECT fts5('tokenize')")
            response = {"status": "PASS_SCOPED_FTS5", "mode": "LOCAL_NO_MODEL",
                        "agentE2E": False}
        elif args.command == "index":
            response = {"results": [add_document(db, args.source_root, rel, args.project_id)
                                    for rel in args.file]}
        else:
            response = {"results": find(db, args.project_id, args.query)}
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, sqlite3.Error, UnicodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2
    finally:
        if "db" in locals(): db.close()


if __name__ == "__main__":
    raise SystemExit(main())

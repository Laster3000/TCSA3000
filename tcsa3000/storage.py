"""Escrituras atomicas y diario encadenado (append-only) de TCSA3000."""
from __future__ import annotations
import datetime as dt, hashlib, json, os
from pathlib import Path

def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()

def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha_file(p) -> str:
    return sha_bytes(Path(p).read_bytes())

def atomic_write(path, data: bytes):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-" + os.urandom(4).hex())
    with open(tmp, "xb") as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)
    if path.read_bytes() != data:
        raise OSError("READBACK_FAILED:" + str(path))

def write_json(path, value):
    atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8"))

def journal(path, op: str, detail: dict) -> str:
    path = Path(path); prev = None
    if path.exists() and path.stat().st_size:
        prev = json.loads(path.read_bytes().splitlines()[-1])["sha"]
    row = {"at": utc(), "op": op, "detail": detail, "prev": prev}
    row["sha"] = sha_bytes(json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    with open(path, "ab") as f:
        f.write((json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))
    return row["sha"]

def verify_journal(path) -> int:
    prev = None; n = 0
    for line in Path(path).read_bytes().splitlines():
        row = json.loads(line); s = row.pop("sha")
        if row["prev"] != prev or sha_bytes(json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8")) != s:
            raise ValueError("JOURNAL_BROKEN_AT:%d" % n)
        prev = s; n += 1
    return n

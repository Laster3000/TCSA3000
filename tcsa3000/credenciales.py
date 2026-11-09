"""Credenciales cifradas con DPAPI (usuario actual de Windows). Nunca se devuelven por la API ni se exportan."""
from __future__ import annotations
import base64, ctypes, json, os, re, secrets as pysecrets
from . import config
from .storage import write_json, utc

NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,63}\Z")

class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]

def _dpapi(data: bytes, protect: bool) -> bytes:
    if os.name != "nt":
        raise OSError("DPAPI_SOLO_WINDOWS")
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    buf = ctypes.create_string_buffer(data, len(data))
    inp = _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))); out = _BLOB()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(inp), None, None, None, None, 0x1, ctypes.byref(out)):  # CRYPTPROTECT_UI_FORBIDDEN
        raise OSError("DPAPI_FALLO")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)

def _file():
    return config.data_dir() / "credenciales.dpapi.json"

def _load() -> dict:
    f = _file()
    return json.loads(f.read_text("utf-8")) if f.exists() else {}

def guardar(nombre: str, valor: str, descripcion: str = "") -> dict:
    if not NAME.fullmatch(nombre or "") or not valor:
        raise ValueError("CREDENCIAL_INVALIDA")
    d = _load()
    d[nombre] = {"cifrado": base64.b64encode(_dpapi(valor.encode("utf-8"), True)).decode(), "descripcion": descripcion[:200], "actualizado": utc()}
    write_json(_file(), d)
    return {"nombre": nombre, "guardado": True}

def leer(nombre: str) -> str | None:
    rec = _load().get(nombre)
    return _dpapi(base64.b64decode(rec["cifrado"]), False).decode("utf-8") if rec else None

def listar() -> list:
    return [{"nombre": k, "descripcion": v.get("descripcion", ""), "actualizado": v.get("actualizado"), "valor": "********"} for k, v in sorted(_load().items())]

def borrar(nombre: str) -> dict:
    d = _load(); existed = d.pop(nombre, None) is not None; write_json(_file(), d)
    return {"nombre": nombre, "borrado": existed}

def token_servicio() -> str:
    """Token local del servicio (lo usan bandeja, panel y adaptador MCP del mismo usuario)."""
    t = leer("tcsa3000-servicio")
    if not t:
        t = pysecrets.token_urlsafe(32); guardar("tcsa3000-servicio", t, "Token local del servicio TCSA3000")
    return t

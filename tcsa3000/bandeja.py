"""Vinculo con TCSA3000.exe (icono de la bandeja).

Norma del usuario (2026-11-09): con el programa cerrado Windows queda limpio. El servicio
(y sus tuneles) solo vive mientras TCSA3000.exe esta abierto. Sin servicio, las IAs siguen
leyendo en modo degradado (solo lectura), como siempre.
Desactivable solo para pruebas: TCSA3000_SIN_BANDEJA=1 o "atadoABandeja": false en la configuracion.
"""
from __future__ import annotations
import ctypes, json, os, subprocess, sys
from . import config


def _f():
    return config.data_dir() / "bandeja.json"


def pid_vivo(pid, exe=None) -> bool:
    if not pid:
        return False
    if os.name != "nt":
        try:
            os.kill(int(pid), 0); return True
        except OSError:
            return False
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, int(pid))
    if not h:
        return False
    try:
        c = ctypes.c_ulong()
        if not k.GetExitCodeProcess(h, ctypes.byref(c)) or c.value != 259:
            return False
        if exe:
            buf = ctypes.create_unicode_buffer(1024); n = ctypes.c_ulong(1024)
            if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
                return buf.value.lower().endswith(exe.lower())
        return True
    finally:
        k.CloseHandle(h)


def viva() -> bool:
    f = _f()
    if not f.exists():
        return False
    try:
        d = json.loads(f.read_text("utf-8"))
    except ValueError:
        return False
    return pid_vivo(d.get("pid"), d.get("exe") or "TCSA3000.exe")


def atado(cfg) -> bool:
    return os.environ.get("TCSA3000_SIN_BANDEJA") != "1" and cfg.get("atadoABandeja", True) is not False


def abrir_icono() -> bool:
    exe = config.home() / "TCSA3000.exe"
    if os.name != "nt" or not exe.is_file():
        return False
    subprocess.Popen([str(exe)], cwd=str(config.home()), close_fds=True, creationflags=0x00000008)
    return True

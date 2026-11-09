"""Ventana de aplicacion independiente para el menu (sin pestanas ni barra de direcciones).

Usa Microsoft Edge en modo aplicacion (--app) con un PERFIL PROPIO de TCSA3000,
asi no se mezcla con el navegador del usuario. Si la ventana ya esta abierta, la trae
al frente y le pide que vaya a la seccion (no abre otra). Al apagar TCSA3000 se
cierra (solo los procesos de este perfil; nunca el Edge del usuario).
Si Edge no existe, abre el navegador por defecto.
"""
from __future__ import annotations
import ctypes
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from . import config

TITULO = "TCSA3000 · Centro de control"
SIN_VENTANA = 0x08000000 if sys.platform == "win32" else 0


def edge():
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if base:
            p = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if p.is_file():
                return p
    return None


def perfil():
    d = config.data_dir() / "ventana"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _buscar_ventana(titulo):
    if sys.platform != "win32":
        return None
    u = ctypes.windll.user32
    encontrada = []
    PROTO = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(hwnd, _):
        if u.IsWindowVisible(hwnd):
            n = u.GetWindowTextLengthW(hwnd)
            if n:
                b = ctypes.create_unicode_buffer(n + 1)
                u.GetWindowTextW(hwnd, b, n + 1)
                if b.value.startswith(titulo):
                    encontrada.append(hwnd)
                    return False
        return True
    u.EnumWindows(PROTO(cb), 0)
    return encontrada[0] if encontrada else None


def _al_frente(hwnd):
    u = ctypes.windll.user32
    if u.IsIconic(hwnd):
        u.ShowWindow(hwnd, 9)  # SW_RESTORE
    u.keybd_event(0x12, 0, 0, 0)  # ALT: permite SetForegroundWindow desde segundo plano
    u.SetForegroundWindow(hwnd)
    u.keybd_event(0x12, 0, 2, 0)


def abrir(url, seccion=""):
    """Abre o trae al frente la ventana del menu. Devuelve como se hizo."""
    hwnd = _buscar_ventana(TITULO)
    if hwnd:
        _al_frente(hwnd)
        return {"ventana": "TRAIDA_AL_FRENTE", "seccion": seccion}
    e = edge()
    destino = url + (("#" + seccion) if seccion else "")
    if not e:
        webbrowser.open(destino)
        return {"ventana": "NAVEGADOR_POR_DEFECTO (no hay Edge)"}
    subprocess.Popen([str(e), "--app=" + destino, f"--user-data-dir={perfil()}", "--window-size=1440,920",
                      "--no-first-run", "--no-default-browser-check", "--disable-features=Translate",
                      "--disable-sync", "--hide-crash-restore-bubble"],
                     close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=0x00000008 if sys.platform == "win32" else 0)
    return {"ventana": "ABIERTA", "modo": "edge --app", "perfil": str(perfil())}


def cerrar():
    """Cierra solo los procesos de Edge que usan el perfil de TCSA3000."""
    if sys.platform != "win32":
        return {"cerradas": 0}
    marca = str(perfil()).replace("'", "''")
    ps = ("$m='" + marca + "'; $n=0; Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
          "Where-Object { $_.CommandLine -and $_.CommandLine.Contains($m) -and $_.CommandLine -notmatch '--type=' } | "
          "ForEach-Object { taskkill /PID $_.ProcessId /T /F | Out-Null; $n++ }; $n")
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                           text=True, timeout=30, creationflags=SIN_VENTANA)
        return {"cerradas": int((r.stdout or "0").strip() or 0)}
    except Exception as e:
        return {"cerradas": 0, "error": str(e)[:200]}

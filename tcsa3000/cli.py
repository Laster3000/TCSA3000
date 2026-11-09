"""CLI y control del servicio: python -m tcsa3000.cli <orden>. Lo usan TCSA3000.cmd y la bandeja."""
from __future__ import annotations
import json, os, subprocess, sys, time, urllib.request, webbrowser
from pathlib import Path
if __package__ in (None, ""):
    _aqui = str(Path(__file__).resolve().parent)
    sys.path[:] = [x for x in sys.path if str(Path(x or ".").resolve()) != _aqui]  # evita sombrear la stdlib
    sys.path.insert(0, str(Path(__file__).resolve().parents[1])); __package__ = "tcsa3000"
from tcsa3000 import VERSION, clients, config, continuidad, espejo, fallback, index, normas, credenciales, service, sources
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

def _health(cfg, timeout=2):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/health" % cfg["port"], timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None

def _post(cfg, path, body=None):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (cfg["port"], path), json.dumps(body or {}).encode(),
                                 {"Content-Type": "application/json", "X-TCSA3000-Token": credenciales.token_servicio()})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())

def estado(cfg):
    h = _health(cfg)
    return {"servicio": "EN_MARCHA" if h else "PARADO", "detalle": h, "ubicacion": cfg["home"], "version": VERSION}

def arrancar(cfg):
    if _health(cfg): return {"servicio": "YA_EN_MARCHA"}
    from . import bandeja
    if bandeja.atado(cfg) and not bandeja.viva():
        # El servicio vive solo con el icono abierto: se abre TCSA3000.exe, que lo arranca.
        if bandeja.abrir_icono():
            for _ in range(80):
                time.sleep(0.25)
                h = _health(cfg)
                if h: return {"servicio": "EN_MARCHA", "pid": h["pid"], "via": "TCSA3000.exe"}
            return {"servicio": "NO_ARRANCO", "ayuda": "Abre TCSA3000.exe"}
    service.lanzar()
    for _ in range(40):
        time.sleep(0.25)
        h = _health(cfg)
        if h: return {"servicio": "EN_MARCHA", "pid": h["pid"]}
    return {"servicio": "NO_ARRANCO", "ayuda": "Revisa data/servicio.journal.jsonl y que el puerto %d este libre" % cfg["port"]}

def parar(cfg):
    if not _health(cfg): return {"servicio": "YA_PARADO"}
    try: _post(cfg, "/api/apagar")
    except Exception: pass
    for _ in range(40):
        time.sleep(0.25)
        if not _health(cfg, 0.5): return {"servicio": "PARADO"}
    st = config.data_dir() / "servicio.json"
    pid = json.loads(st.read_text("utf-8")).get("pid") if st.exists() else None
    if pid and os.name == "nt":
        q = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine" % int(pid)], capture_output=True, text=True, timeout=15, creationflags=SIN_VENTANA).stdout
        if "service.py" in q and "tcsa3000" in q.lower():
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, creationflags=SIN_VENTANA)
            return {"servicio": "PARADO_FORZADO", "pid": pid}
    return {"servicio": "NO_SE_PUDO_PARAR_VERIFICAR_A_MANO"}

def respaldo(cfg):
    if _health(cfg):
        d = _post(cfg, "/api/respaldo")
    else:
        from tcsa3000 import espejo_github
        d = {"contextoFallback": fallback.exportar(cfg, estado(cfg)), "github": espejo_github.sincronizar(cfg) if espejo_github.configurado(cfg) else None,
             "espejoDrive": espejo.sincronizar(cfg)}
    e = d["espejoDrive"]
    g = d.get("github") or {}
    txt = ("Respaldo al dia: %d subidos a Drive, %d traidos de Drive" % (e["subidosADrive"], e["importadosDeDrive"])) if e.get("estado") == "OK" else ("Respaldo " + str(e.get("motivo") or e.get("estado")))
    if g: txt += "; GitHub: " + (("%d subidos" % g.get("subidos", 0)) if g.get("estado") == "OK" else str(g.get("estado")))
    return {"estado": txt, "detalle": d}

def panel(cfg, pestana=""):
    if not _health(cfg): arrancar(cfg)
    webbrowser.open("http://127.0.0.1:%d/panel?t=%s%s" % (cfg["port"], credenciales.token_servicio(), ("#" + pestana) if pestana else ""))
    return {"panel": "ABIERTO"}

def main(argv=None):
    a = argv if argv is not None else sys.argv[1:]
    cmd = a[0] if a else "estado"; cfg = config.load()
    if cmd == "estado": r = estado(cfg)
    elif cmd == "arrancar": r = arrancar(cfg)
    elif cmd == "parar": r = parar(cfg)
    elif cmd == "reiniciar": parar(cfg); r = arrancar(cfg)
    elif cmd == "panel": r = panel(cfg, a[1] if len(a) > 1 else "")
    elif cmd == "ubicacion": r = {"ubicacion": cfg["home"], "clientes": [{"ruta": str(p), "tcsa3000": (json.loads(p.read_text("utf-8-sig")).get("mcpServers", {}).get("tcsa3000") or {}).get("env", {}).get("TCSA3000_HOME")} for p in clients.claude_configs()]}
    elif cmd == "directrices": r = normas.leer()
    elif cmd == "reindexar": r = index.reindex(cfg)
    elif cmd == "respaldo": r = respaldo(cfg)
    elif cmd == "verificar-respaldo": r = espejo.verificar(cfg)
    elif cmd == "buscar": db = index.connect(); r = index.search(db, " ".join(a[1:])); db.close()
    elif cmd == "lista": r = sources.lista(cfg)
    elif cmd == "descubrimientos": r = sources.descubrimientos(cfg)
    elif cmd == "registrar-claude": r = [clients.registrar(p) for p in clients.claude_configs()]
    elif cmd == "snippet": r = clients.snippet()
    elif cmd == "arranque": r = continuidad.arranque(cfg)
    elif cmd == "menu": r = continuidad.menu(cfg)
    elif cmd == "reanudar": r = continuidad.reanudar(cfg, a[1] if len(a) > 1 else "")
    else: r = {"error": "ORDEN_DESCONOCIDA", "ordenes": "estado arrancar parar reiniciar panel [seccion] ubicacion arranque menu reanudar <ID> directrices reindexar respaldo verificar-respaldo buscar lista descubrimientos registrar-claude snippet"}
    if sys.stdout is not None:  # con pythonw y sin redireccion no hay consola
        print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

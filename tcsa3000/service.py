"""Servicio local TCSA3000: HTTP en 127.0.0.1, MCP JSON-RPC en /mcp, panel en /panel. Proceso unico controlado por bandeja/panel/CLI.
Uso: python -m tcsa3000.service   (o tcsa3000\\service.py)"""
from __future__ import annotations
import html, json, os, subprocess, sys, threading, time
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
if __package__ in (None, ""):
    _aqui = str(Path(__file__).resolve().parent)
    sys.path[:] = [x for x in sys.path if str(Path(x or ".").resolve()) != _aqui]  # evita sombrear la stdlib
    sys.path.insert(0, str(Path(__file__).resolve().parents[1])); __package__ = "tcsa3000"
from tcsa3000 import VERSION, clients, config, fallback, index, normas, credenciales, sources, tools
from tcsa3000.storage import journal, utc, write_json

STARTED = time.time()

def state_file():
    return config.data_dir() / "servicio.json"

def panel_html(port: int) -> str:
    return (Path(__file__).with_name("panel.html").read_text("utf-8")).replace("{{VERSION}}", VERSION).replace("{{PORT}}", str(port))

class H(BaseHTTPRequestHandler):
    server_version = "TCSA3000/" + VERSION
    def log_message(self, *a): pass
    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        b = body if isinstance(body, bytes) else (json.dumps(body, ensure_ascii=False, indent=1).encode("utf-8") if not isinstance(body, str) else body.encode("utf-8"))
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store"); self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)
    def _token_ok(self) -> bool:
        tok = self.server.token
        if self.headers.get("X-TCSA3000-Token") == tok: return True
        c = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return "tcsa3000" in c and c["tcsa3000"].value == tok
    def _origin_ok(self) -> bool:
        o = self.headers.get("Origin")
        return o in (None, "http://127.0.0.1:%d" % self.server.port, "http://localhost:%d" % self.server.port)
    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 400_000: raise ValueError("CUERPO_DEMASIADO_GRANDE")
        return json.loads(self.rfile.read(n) or b"{}")
    def do_GET(self):
        u = urlparse(self.path); cfg = self.server.cfg
        if u.path == "/health":
            return self._send(200, {"status": "OK", "version": VERSION, "pid": os.getpid(), "uptimeS": int(time.time() - STARTED), "ubicacion": cfg["home"]})
        if u.path == "/panel":
            t = parse_qs(u.query).get("t", [None])[0]
            if t and t == self.server.token:
                return self._send(303, "", "text/plain", {"Location": "/panel", "Set-Cookie": "tcsa3000=%s; HttpOnly; SameSite=Strict; Path=/" % t})
            if not self._token_ok(): return self._send(401, "<h1>401</h1><p>Abre el panel desde la bandeja o con TCSA3000.cmd panel.</p>", "text/html; charset=utf-8")
            return self._send(200, panel_html(self.server.port), "text/html; charset=utf-8")
        if u.path == "/mcp": return self._send(405, {"error": "USA_POST"}, extra={"Allow": "POST"})
        if not self._token_ok(): return self._send(401, {"error": "NO_AUTORIZADO"})
        try:
            if u.path == "/api/estado": return self._send(200, self.server.estado())
            if u.path == "/api/directrices": return self._send(200, normas.leer())
            if u.path == "/api/credenciales": return self._send(200, credenciales.listar())
            if u.path == "/api/clientes": return self._send(200, {"claude": [{"ruta": str(p), "registrado": self.server.registrado(p)} for p in clients.claude_configs()], "otros": clients.snippet(self.server.token, self.server.port)})
            if u.path == "/api/lista": return self._send(200, sources.lista(cfg))
            if u.path == "/api/descubrimientos": return self._send(200, sources.descubrimientos(cfg))
            if u.path == "/api/propuestas": return self._send(200, sources.propuestas())
            if u.path == "/api/config": return self._send(200, {k: v for k, v in cfg.items()})
            if u.path == "/api/herramientas": return self._send(200, [{"name": t["name"], "description": t["description"], "escritura": t["name"] in tools.ESCRITURA} for t in tools.TOOLS])
        except Exception as e:
            return self._send(500, {"error": str(e)})
        self._send(404, {"error": "NO_ENCONTRADO"})
    def do_POST(self):
        u = urlparse(self.path); cfg = self.server.cfg
        if not self._token_ok() or not self._origin_ok(): return self._send(401, {"error": "NO_AUTORIZADO"})
        try:
            body = self._body()
            if u.path == "/mcp":
                if isinstance(body, list):
                    out = [r for r in (tools.handle_jsonrpc(m, cfg) for m in body) if r]
                else:
                    out = tools.handle_jsonrpc(body, cfg)
                return self._send(202, b"", "text/plain") if out in (None, []) else self._send(200, out)
            if u.path == "/api/tool":
                r = tools.call(body.get("name", ""), body.get("arguments") or {}, cfg, "SERVICIO")
                if body.get("name") in tools.ESCRITURA:
                    journal(config.data_dir() / "servicio.journal.jsonl", "PANEL_TOOL", {"name": body.get("name")})
                return self._send(200, r)
            if u.path == "/api/normas":
                r = normas.actualizar(body.get("texto", ""), body.get("sha256", ""), body.get("actor", "panel"))
                journal(config.data_dir() / "servicio.journal.jsonl", "NORMAS", r); return self._send(200, r)
            if u.path == "/api/credenciales":
                if body.get("borrar"): return self._send(200, credenciales.borrar(body["nombre"]))
                return self._send(200, credenciales.guardar(body.get("nombre", ""), body.get("valor", ""), body.get("descripcion", "")))
            if u.path == "/api/registrar":
                p = Path(body.get("ruta", ""))
                if p not in clients.claude_configs(): raise ValueError("RUTA_CLIENTE_NO_DETECTADA")
                r = clients.registrar(p, bool(body.get("quitar")))
                journal(config.data_dir() / "servicio.journal.jsonl", "REGISTRO_MCP", r); return self._send(200, r)
            if u.path == "/api/config":
                r = self.server.guardar_config(body); return self._send(200, r)
            if u.path == "/api/proponer":
                return self._send(200, sources.proponer(body.get("tipo"), body.get("titulo"), body.get("projectId"), body.get("resumen"), body.get("fuente", ""), "panel"))
            if u.path == "/api/reindexar": return self._send(200, index.reindex(cfg))
            if u.path == "/api/respaldo": return self._send(200, fallback.exportar(cfg, self.server.estado()))
            if u.path == "/api/apagar":
                self._send(200, {"estado": "APAGANDO"}); threading.Thread(target=self.server.apagar, daemon=True).start(); return
            if u.path == "/api/reiniciar":
                self._send(200, {"estado": "REINICIANDO"}); threading.Thread(target=self.server.reiniciar, daemon=True).start(); return
        except Exception as e:
            return self._send(400, {"error": "%s: %s" % (type(e).__name__, e)})
        self._send(404, {"error": "NO_ENCONTRADO"})

class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, cfg, token):
        self.cfg, self.token, self.port = cfg, token, cfg["port"]
        super().__init__((cfg["host"], cfg["port"]), H)
        self._stop = threading.Event()
    def registrado(self, p):
        try:
            e = json.loads(Path(p).read_text("utf-8-sig")).get("mcpServers", {}).get("tcsa3000")
            if not e: return "NO"
            return "SI" if e.get("env", {}).get("TCSA3000_HOME") == self.cfg["home"] else "SI_OTRA_UBICACION:" + str(e.get("env", {}).get("TCSA3000_HOME"))
        except Exception as ex:
            return "ERROR:" + str(ex)
    def estado(self):
        return {"servicio": "EN_MARCHA", "version": VERSION, "pid": os.getpid(), "puerto": self.port, "ubicacion": self.cfg["home"],
                "tcsaRoot": self.cfg["tcsaRoot"], "tcsaAccesible": Path(self.cfg["tcsaRoot"]).is_dir(), "respaldoDrive": self.cfg["fallbackDir"],
                "inicio": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(STARTED)), "python": sys.executable}
    def guardar_config(self, body: dict):
        allowed = {"tcsaRoot", "fallbackDir", "port", "fallbackEveryMinutes", "allowlist"}
        bad = set(body) - allowed
        if bad: raise ValueError("CLAVES_NO_PERMITIDAS:" + ",".join(sorted(bad)))
        p = config.config_path(); cur = json.loads(p.read_text("utf-8-sig")) if p.exists() else {}
        if p.exists():
            pre = config.home() / "VERSIONES" / "config" / ("tcsa3000.config-%s.json" % utc().replace(":", "")[:17]); pre.parent.mkdir(parents=True, exist_ok=True); pre.write_bytes(p.read_bytes())
        cur.update(body); write_json(p, cur); self.cfg = config.load()
        journal(config.data_dir() / "servicio.journal.jsonl", "CONFIG", {"claves": sorted(body)})
        return {"guardado": True, "config": self.cfg, "nota": "Cambiar el puerto requiere reiniciar el servicio."}
    def apagar(self):
        time.sleep(0.3); journal(config.data_dir() / "servicio.journal.jsonl", "APAGADO", {"pid": os.getpid()})
        self._stop.set(); self.shutdown()
    def reiniciar(self):
        lanzar(esperar=True); self.apagar()
    def ciclo(self):
        try: index.reindex(self.cfg)
        except Exception: pass
        nxt = time.time() + 5
        while not self._stop.wait(1):
            if time.time() >= nxt:
                nxt = time.time() + 60 * max(1, int(self.cfg["fallbackEveryMinutes"]))
                try: index.reindex(self.cfg)  # la busqueda incluye lo guardado desde el ultimo ciclo
                except Exception: pass
                try: journal(config.data_dir() / "servicio.journal.jsonl", "RESPALDO", fallback.exportar(self.cfg, self.estado()))
                except Exception as e: journal(config.data_dir() / "servicio.journal.jsonl", "RESPALDO_ERROR", {"error": str(e)})

def lanzar(esperar=False):
    args = [config.python_exe(True), "-B", str(Path(__file__).resolve())] + (["--esperar"] if esperar else [])
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    env = dict(os.environ, TCSA3000_HOME=str(config.home()))
    return subprocess.Popen(args, cwd=str(config.home()), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True)

def main():
    cfg = config.load()
    if "--esperar" in sys.argv:
        time.sleep(1.5)
    srv = Server(cfg, credenciales.token_servicio())
    write_json(state_file(), {"pid": os.getpid(), "puerto": cfg["port"], "inicio": utc(), "version": VERSION, "ubicacion": cfg["home"]})
    journal(config.data_dir() / "servicio.journal.jsonl", "ARRANQUE", {"pid": os.getpid(), "puerto": cfg["port"]})
    threading.Thread(target=srv.ciclo, daemon=True).start()
    try:
        srv.serve_forever(poll_interval=0.5)
    finally:
        srv.server_close()

if __name__ == "__main__":
    main()

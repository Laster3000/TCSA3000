"""Servicio local TCSA3000: HTTP en 127.0.0.1, MCP JSON-RPC en /mcp, panel en /panel. Proceso unico controlado por bandeja/panel/CLI.
Uso: python -m tcsa3000.service   (o tcsa3000\\service.py)"""
from __future__ import annotations
import hmac, html, json, os, re, subprocess, sys, threading, time
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
if __package__ in (None, ""):
    _aqui = str(Path(__file__).resolve().parent)
    sys.path[:] = [x for x in sys.path if str(Path(x or ".").resolve()) != _aqui]  # evita sombrear la stdlib
    sys.path.insert(0, str(Path(__file__).resolve().parents[1])); __package__ = "tcsa3000"
from tcsa3000 import VERSION, clients, config, continuidad, espejo, fallback, index, normas, credenciales, sources, tools, tunel, openai_tunel, historial, conexiones, espejo_github
from tcsa3000.storage import journal, utc, write_json

STARTED = time.time()
REMOTO = re.compile(r"^/remoto/([A-Za-z0-9_-]{20,})/mcp/?$")
OPENAI = re.compile(r"^/openai/([A-Za-z0-9_-]{20,})/mcp/?$")
CONEXION = re.compile(r"^/cx/([a-z0-9][a-z0-9-]{1,39})/([A-Za-z0-9_-]{20,})/mcp/?$")

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
        if u.path.startswith("/.well-known/"):
            # Descubrimiento OAuth (RFC 9728/8414): este MCP no usa OAuth. 404 = "sin metadatos", que es lo que esperan
            # los clientes (tunnel-client de OpenAI) para continuar sin autenticacion. No da acceso a nada.
            return self._send(404, {"error": "NOT_FOUND"})
        if u.path == "/mcp" or REMOTO.match(u.path) or OPENAI.match(u.path) or CONEXION.match(u.path): return self._send(405, {"error": "USA_POST"}, extra={"Allow": "POST"})
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
            if u.path == "/api/inventario-credenciales":
                raices = [x.get("sourceRoot") or x.get("currentRuntimeRoot") for x in continuidad._catalogo(continuidad.root(cfg))[1].get("projects", [])]
                return self._send(200, credenciales.inventario([r for r in raices if r] + [cfg["home"]]))
            if u.path == "/api/tunel": return self._send(200, tunel.estado(cfg))
            if u.path == "/api/openai-tunel": return self._send(200, openai_tunel.estado(cfg))
            if u.path == "/api/conexiones": return self._send(200, {"conexiones": conexiones.estado(cfg), "tunnelClient": openai_tunel.estado(cfg).get("version"),
                                                               "tunnelClientInstalado": openai_tunel.exe().is_file(), "cloudflaredInstalado": tunel.exe().is_file()})
            if u.path == "/api/github": return self._send(200, {"config": {"repo": cfg.get("githubRespaldoRepo") or "", "rama": cfg.get("githubRespaldoRama") or "",
                                                                      "repoPublico": cfg.get("githubPublicoRepo") or "", "publicoAuto": bool(cfg.get("githubPublicoAuto"))},
                                                           "tokenGuardado": credenciales.leer(espejo_github.CRED) is not None, "tokenPublicoPropio": credenciales.leer(espejo_github.CRED_PUB) is not None,
                                                           "ultimo": self.server.ultimo_github, "ultimoPublico": self.server.ultimo_publico})
            if u.path == "/api/espejo": return self._send(200, self.server.ultimo_espejo or {"estado": "AUN_NO_EJECUTADO"})
            if u.path == "/api/historial":
                q = parse_qs(u.query)
                return self._send(200, historial.leer(q.get("fallos", ["0"])[0] == "1", q.get("fuente", [""])[0], q.get("texto", [""])[0], int(q.get("limite", ["300"])[0])))
            if u.path == "/api/herramientas": return self._send(200, [{"name": t["name"], "description": t["description"], "escritura": t["name"] in tools.ESCRITURA} for t in tools.TOOLS])
        except Exception as e:
            historial.registrar_error("panel:GET " + u.path, str(e))
            return self._send(500, {"error": str(e)})
        self._send(404, {"error": "NO_ENCONTRADO"})
    def _remoto(self, secreto_url: str, canal: str = "cloudflare", cid: str | None = None):
        cfg = self.server.cfg
        if cid:
            try: cx = conexiones.obtener(cid)
            except LookupError: time.sleep(0.5); return self._send(404, {"error": "NO_ENCONTRADO"})
            esperado = conexiones.secreto(cid)
        else:
            esperado = openai_tunel.secreto() if canal == "openai" else tunel.secreto()
        if not hmac.compare_digest(secreto_url, esperado):
            time.sleep(0.5); return self._send(404, {"error": "NO_ENCONTRADO"})
        if cid:
            if cx.get("auth") == "oauth":
                return self._send(501, {"error": "OAUTH_NO_DISPONIBLE", "ayuda": "Esta conexion esta guardada con OAuth, que TCSA3000 aun no emite. Usa 'ninguna' o 'token'."})
            if cx.get("auth") == "token":
                tok = credenciales.leer("tcsa3000-token-" + cid) or ""
                if not tok or not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + tok):
                    historial.registrar_error("conexion:" + cid, "Token Bearer ausente o incorrecto")
                    return self._send(401, {"error": "TOKEN_REQUERIDO"}, extra={"WWW-Authenticate": "Bearer"})
            escribe = bool(cx.get("escritura")); canal = "cx:" + cid
        else:
            escribe = cfg.get("openaiEscritura", True) if canal == "openai" else cfg.get("remotoEscritura")
        modo = "REMOTO_ESCRITURA" if escribe else "REMOTO_LECTURA"
        try:
            body = self._body()
        except Exception:
            return self._send(400, {"error": "JSON_INVALIDO"})
        msgs = body if isinstance(body, list) else [body]
        out = []
        for m in msgs:
            if not isinstance(m, dict): continue
            r = tools.handle_jsonrpc(m, cfg, modo, "remoto:" + canal)
            if m.get("method") == "tools/call":
                res = (r or {}).get("result") or {}
                fallo = bool(res.get("isError")) or "error" in (r or {})
                txt = ""
                if fallo:
                    try: txt = (res.get("content") or [{}])[0].get("text", "")[:300] if res else str(r.get("error"))[:300]
                    except Exception: txt = "?"
                journal(config.data_dir() / "remoto.journal.jsonl", "REMOTO_TOOL", {"name": (m.get("params") or {}).get("name"), "modo": modo, "canal": canal,
                        "agente": ((m.get("params") or {}).get("arguments") or {}).get("agente"), "ok": not fallo, "error": txt or None})
            if r: out.append(r)
        if not out: return self._send(202, b"", "text/plain")
        return self._send(200, out if isinstance(body, list) else out[0])
    def do_POST(self):
        u = urlparse(self.path); cfg = self.server.cfg
        m = REMOTO.match(u.path)
        if m: return self._remoto(m.group(1))
        m = OPENAI.match(u.path)
        if m: return self._remoto(m.group(1), "openai")
        m = CONEXION.match(u.path)
        if m: return self._remoto(m.group(2), cid=m.group(1))
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
                r = self.server.guardar_config(body)
                if any(k.startswith("github") for k in body): self.server.github_ahora()
                return self._send(200, r)
            if u.path == "/api/proponer":
                return self._send(200, sources.proponer(body.get("tipo"), body.get("titulo"), body.get("projectId"), body.get("resumen"), body.get("fuente", ""), "panel"))
            if u.path == "/api/reindexar": return self._send(200, index.reindex(cfg))
            if u.path == "/api/respaldo": return self._send(200, self.server.respaldar())
            if u.path == "/api/github/comprobar": return self._send(200, espejo_github.comprobar(self.server.cfg))
            if u.path == "/api/github/token":
                v = (body.get("valor") or "").strip()
                if len(v) < 20: raise ValueError("TOKEN_INVALIDO")
                r = credenciales.guardar(espejo_github.CRED, v, "Token de GitHub de TCSA3000 (Contents RW en los repositorios elegidos)")
                self.server.github_ahora(); return self._send(200, r)
            if u.path == "/api/github/comprobar-publico": return self._send(200, espejo_github.comprobar_publico(self.server.cfg))
            if u.path == "/api/github/publicar":
                self.server.ultimo_publico = espejo_github.publicar(self.server.cfg); return self._send(200, self.server.ultimo_publico)
            if u.path == "/api/github/sincronizar":
                self.server.ultimo_github = espejo_github.sincronizar(self.server.cfg); return self._send(200, self.server.ultimo_github)
            if u.path == "/api/espejo/verificar": return self._send(200, espejo.verificar(cfg))
            if u.path == "/api/conexiones/guardar": return self._send(200, conexiones.guardar(body))
            if u.path == "/api/conexiones/borrar": return self._send(200, conexiones.borrar(body.get("id", "")))
            if u.path == "/api/conexiones/iniciar": return self._send(200, conexiones.iniciar(self.server.cfg, body.get("id", "")))
            if u.path == "/api/conexiones/parar": return self._send(200, conexiones.parar(body.get("id", "")))
            if u.path == "/api/conexiones/importar-clave":
                c = conexiones.obtener(body.get("id", ""))
                return self._send(200, openai_tunel.importar_de_windows(body.get("objetivo") or "MMC55.AI.TUNNEL.RUNTIME", c.get("credencial") or "openai-runtime-" + c["id"]))
            if u.path == "/api/openai-tunel/descargar": return self._send(200, openai_tunel.descargar())
            if u.path == "/api/openai-tunel/importar": return self._send(200, openai_tunel.importar_de_windows())
            if u.path == "/api/openai-tunel/clave":
                v = (body.get("valor") or "").strip()
                if len(v) < 20: raise ValueError("CLAVE_INVALIDA")
                return self._send(200, credenciales.guardar(openai_tunel.CRED, v, "Clave de runtime del Secure MCP Tunnel de OpenAI"))
            if u.path == "/api/openai-tunel/iniciar": return self._send(200, openai_tunel.iniciar(self.server.cfg))
            if u.path == "/api/openai-tunel/parar": return self._send(200, openai_tunel.parar(cfg))
            if u.path == "/api/tunel/descargar": return self._send(200, tunel.descargar())
            if u.path == "/api/tunel/iniciar": return self._send(200, tunel.iniciar(cfg))
            if u.path == "/api/tunel/parar": return self._send(200, tunel.parar(cfg))
            if u.path == "/api/tunel/rotar": tunel.parar(cfg); return self._send(200, tunel.rotar_secreto())
            if u.path == "/api/apagar":
                self._send(200, {"estado": "APAGANDO"}); threading.Thread(target=self.server.apagar, daemon=True).start(); return
            if u.path == "/api/reiniciar":
                self._send(200, {"estado": "REINICIANDO"}); threading.Thread(target=self.server.reiniciar, daemon=True).start(); return
        except Exception as e:
            historial.registrar_error("panel:POST " + u.path, "%s: %s" % (type(e).__name__, e))
            return self._send(400, {"error": "%s: %s" % (type(e).__name__, e)})
        self._send(404, {"error": "NO_ENCONTRADO"})

class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, cfg, token):
        self.cfg, self.token, self.port = cfg, token, cfg["port"]
        super().__init__((cfg["host"], cfg["port"]), H)
        self._stop = threading.Event()
        self.ultimo_espejo = None
        self.ultimo_github = None
        self.ultimo_publico = None
    def registrado(self, p):
        try:
            e = json.loads(Path(p).read_text("utf-8-sig")).get("mcpServers", {}).get("tcsa3000")
            if not e: return "NO"
            return "SI" if e.get("env", {}).get("TCSA3000_HOME") == self.cfg["home"] else "SI_OTRA_UBICACION:" + str(e.get("env", {}).get("TCSA3000_HOME"))
        except Exception as ex:
            return "ERROR:" + str(ex)
    def estado(self):
        return {"servicio": "EN_MARCHA", "version": VERSION, "pid": os.getpid(), "puerto": self.port, "ubicacion": self.cfg["home"],
                "tcsaRoot": self.cfg["tcsaRoot"], "tcsaAccesible": Path(self.cfg["tcsaRoot"]).is_dir(), "respaldoDrive": self.cfg["respaldoDir"],
                "respaldoAccesible": Path(self.cfg["respaldoDir"]).parent.exists(), "ultimoEspejo": (self.ultimo_espejo or {}).get("at"),
                "github": {"repo": self.cfg.get("githubRespaldoRepo") or None, "ultimo": (self.ultimo_github or {}).get("at"), "estado": (self.ultimo_github or {}).get("estado"),
                           "ayuda": (self.ultimo_github or {}).get("ayuda"), "sincronizando": bool(getattr(self, "gh_ocupado", False))},
                "githubPublico": {"repo": self.cfg.get("githubPublicoRepo") if self.cfg.get("githubPublicoAuto") else None, "ultimo": (self.ultimo_publico or {}).get("at"),
                                  "estado": (self.ultimo_publico or {}).get("estado"), "ayuda": (self.ultimo_publico or {}).get("ayuda")},
                "inicio": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(STARTED)), "python": sys.executable}
    def guardar_config(self, body: dict):
        allowed = {"tcsaRoot", "respaldoDir", "fallbackDir", "port", "fallbackEveryMinutes", "allowlist", "remotoEscritura", "tunelAlArrancar", "tunelHost", "openaiTunnelId", "openaiEscritura", "openaiTunelAlArrancar", "githubRespaldoRepo", "githubRespaldoRama", "githubPublicoRepo", "githubPublicoRama", "githubPublicoAuto"}
        bad = set(body) - allowed
        if bad: raise ValueError("CLAVES_NO_PERMITIDAS:" + ",".join(sorted(bad)))
        p = config.config_path(); cur = json.loads(p.read_text("utf-8-sig")) if p.exists() else {}
        if p.exists():
            pre = config.home() / "VERSIONES" / "config" / ("tcsa3000.config-%s.json" % utc().replace(":", "")[:17]); pre.parent.mkdir(parents=True, exist_ok=True); pre.write_bytes(p.read_bytes())
        cur.update(body); write_json(p, cur); self.cfg = config.load()
        journal(config.data_dir() / "servicio.journal.jsonl", "CONFIG", {"claves": sorted(body)})
        return {"guardado": True, "config": self.cfg, "nota": "Cambiar el puerto requiere reiniciar el servicio."}
    def github_ahora(self):
        """Sincroniza GitHub (privado y publico) en segundo plano, sin esperar al ciclo."""
        if getattr(self, "gh_ocupado", False): return
        def tarea():
            self.gh_ocupado = True
            try:
                if espejo_github.configurado(self.cfg):
                    try: self.ultimo_github = espejo_github.sincronizar(self.cfg)
                    except Exception as e: self.ultimo_github = {"estado": "ERROR", "error": str(e), "at": utc()}
                    if self.ultimo_github.get("estado") != "OK": historial.registrar_error("respaldo:github", json.dumps(self.ultimo_github, ensure_ascii=False)[:600])
                if self.cfg.get("githubPublicoAuto") and self.cfg.get("githubPublicoRepo") and espejo_github.token(True):
                    try: self.ultimo_publico = espejo_github.publicar(self.cfg)
                    except Exception as e: self.ultimo_publico = {"estado": "ERROR", "error": str(e), "at": utc()}
                    if self.ultimo_publico.get("estado") != "OK": historial.registrar_error("github:publico", json.dumps(self.ultimo_publico, ensure_ascii=False)[:600])
            finally:
                self.gh_ocupado = False
        threading.Thread(target=tarea, daemon=True).start()
    def respaldar(self):
        fb = fallback.exportar(self.cfg, self.estado())
        self.gh_ocupado = True
        if espejo_github.configurado(self.cfg):  # 2o respaldo: GitHub privado
            try: self.ultimo_github = espejo_github.sincronizar(self.cfg)
            except Exception as e: self.ultimo_github = {"estado": "ERROR", "error": str(e), "at": utc()}
            if self.ultimo_github.get("estado") != "OK":
                historial.registrar_error("respaldo:github", json.dumps(self.ultimo_github, ensure_ascii=False)[:600])
        if self.cfg.get("githubPublicoAuto") and self.cfg.get("githubPublicoRepo"):
            try: self.ultimo_publico = espejo_github.publicar(self.cfg)
            except Exception as e: self.ultimo_publico = {"estado": "ERROR", "error": str(e), "at": utc()}
            if self.ultimo_publico.get("estado") != "OK":
                historial.registrar_error("github:publico", json.dumps(self.ultimo_publico, ensure_ascii=False)[:600])
        try: self.ultimo_espejo = espejo.sincronizar(self.cfg)
        except Exception as e: self.ultimo_espejo = {"estado": "ERROR", "error": str(e), "at": utc()}
        self.gh_ocupado = False
        if (self.ultimo_espejo or {}).get("estado") not in ("OK", None):
            historial.registrar_error("respaldo:drive", json.dumps(self.ultimo_espejo, ensure_ascii=False)[:600])
        journal(config.data_dir() / "servicio.journal.jsonl", "RESPALDO", {"fallback": fb.get("estado"),
                "github": {k: (self.ultimo_github or {}).get(k) for k in ("estado", "subidos", "importados", "commit")}, "espejo": {k: self.ultimo_espejo.get(k) for k in ("estado", "subidosADrive", "importadosDeDrive", "conflictos")}})
        return {"contextoFallback": fb, "github": self.ultimo_github, "espejoDrive": self.ultimo_espejo}
    def apagar(self):
        time.sleep(0.3); journal(config.data_dir() / "servicio.journal.jsonl", "APAGADO", {"pid": os.getpid()})
        for t in (tunel, openai_tunel):
            try: t.parar(self.cfg)
            except Exception: pass
        conexiones.parar_todas()
        self._stop.set(); self.shutdown()
    def reiniciar(self):
        lanzar(esperar=True); self.apagar()
    def ciclo(self):
        try: index.reindex(self.cfg)
        except Exception: pass
        if self.cfg.get("tunelAlArrancar"):
            try: tunel.iniciar(self.cfg)
            except Exception: pass
        try:
            conexiones.migrar_desde_config(self.cfg)
            conexiones.arrancar_automaticas(self.cfg)
        except Exception as e:
            historial.registrar_error("conexiones", str(e))
        nxt = time.time() + 5
        while not self._stop.wait(1):
            if time.time() >= nxt:
                nxt = time.time() + 60 * max(1, int(self.cfg["fallbackEveryMinutes"]))
                try: index.reindex(self.cfg)  # la busqueda incluye lo guardado desde el ultimo ciclo
                except Exception: pass
                try: self.respaldar()
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

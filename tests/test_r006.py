"""R006: tunel robusto (UTF-8, concesion por canal, errores visibles), historial, conexiones multiples, GitHub privado e instrucciones."""
import json, os, subprocess, sys, threading, unittest
from pathlib import Path
from unittest import mock
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
_m = sys.modules.get("tcsa3000")
if _m is not None and not hasattr(_m, "__path__"):
    del sys.modules["tcsa3000"]
from tcsa3000 import conexiones, continuidad as C, espejo_github, historial, instrucciones, tools
from tests.test_r003 import Base

class Concesion(Base):
    def test_mismo_canal_remoto_no_se_bloquea_y_otro_si(self):
        a = C.abrir_proyecto(self.cfg, "AF-CORE", "ChatGPT turno 1", canal="remoto:cx:chatgpt")
        self.assertIn("lease", a)
        b = C.abrir_proyecto(self.cfg, "AF-CORE", "ChatGPT turno 2 ñ", canal="remoto:cx:chatgpt")
        self.assertIn("lease", b)  # renovada, no PROYECTO_EN_USO
        C.cierre(self.cfg, "AF-CORE", "C1", "sin token, mismo canal", next_action="x", agente="otro nombre", canal="remoto:cx:chatgpt")
        self.assertEqual(C.abrir_proyecto(self.cfg, "AF-CORE", "Claude Desktop")["estado"], "PROYECTO_EN_USO")
        with self.assertRaises(PermissionError): C.cierre(self.cfg, "AF-CORE", "C1", "x", next_action="y", agente="Claude Desktop")

class Errores(Base):
    def test_error_de_herramienta_queda_en_historial(self):
        r = tools.handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "tcsa3000_reanudar", "arguments": {"projectId": "NO-EXISTE"}}}, self.cfg)
        self.assertTrue(r["result"]["isError"])
        h = historial.leer(solo_fallos=True)
        self.assertTrue(any("NO-EXISTE" in json.dumps(e, ensure_ascii=False) for e in h["eventos"]))
    def test_estado_dice_escritura_en_remoto_escritura(self):
        from tcsa3000 import index
        index.reindex(self.cfg)
        self.assertTrue(tools.call("tcsa3000_estado", {}, self.cfg, "REMOTO_ESCRITURA")["escrituraPermitida"])
        self.assertFalse(tools.call("tcsa3000_estado", {}, self.cfg, "REMOTO_LECTURA")["escrituraPermitida"])
    def test_anotaciones_de_herramientas(self):
        t = {x["name"]: x for x in tools.lista_para("REMOTO_ESCRITURA")}
        self.assertTrue(t["tcsa3000_lista"]["annotations"]["readOnlyHint"])
        self.assertFalse(t["tcsa3000_cierre"]["annotations"]["readOnlyHint"])
        self.assertFalse(t["tcsa3000_cierre"]["annotations"]["destructiveHint"])

class Conexiones(Base):
    def test_guardar_varias_y_validar(self):
        conexiones.guardar({"id": "chatgpt-a", "nombre": "A", "tipo": "openai-tunel", "auth": "ninguna", "tunnelId": "tunnel_" + "a" * 32, "escritura": True})
        conexiones.guardar({"id": "local-http", "nombre": "B", "tipo": "url-http", "auth": "ninguna", "escritura": False})
        with mock.patch.object(conexiones.credenciales, "secreto_sistema", return_value="S" * 30):
            est = {e["id"]: e for e in conexiones.estado(self.cfg)}
        self.assertEqual(set(est), {"chatgpt-a", "local-http"}); self.assertIn("/cx/local-http/", est["local-http"]["url"])
        with self.assertRaises(ValueError): conexiones.guardar({"id": "x", "tipo": "openai-tunel"})
        with self.assertRaises(ValueError): conexiones.guardar({"id": "mala", "tipo": "ftp"})
        with self.assertRaises(ValueError): conexiones.guardar({"id": "t", "tipo": "openai-tunel", "tunnelId": "tunnel_corto"})
        self.assertEqual(conexiones.iniciar(self.cfg, "chatgpt-a")["estado"], "FALTA_TUNNEL_CLIENT") if not conexiones.openai_tunel.exe().is_file() else None
        conexiones.borrar("local-http"); self.assertEqual([c["id"] for c in conexiones.listar_crudo()], ["chatgpt-a"])
    def test_migracion_de_config_antigua(self):
        cfg = dict(self.cfg, openaiTunnelId="tunnel_" + "b" * 32, openaiEscritura=True, openaiTunelAlArrancar=True)
        conexiones.migrar_desde_config(cfg)
        c = conexiones.listar_crudo()[0]
        self.assertEqual((c["id"], c["tipo"], c["alArrancar"], c["escritura"]), ("chatgpt-tunel", "openai-tunel", True, True))

class GitHub(Base):
    def test_bloquea_repositorio_publico_y_sin_configurar(self):
        self.assertEqual(espejo_github.comprobar(self.cfg)["estado"], "SIN_CONFIGURAR")
        cfg = dict(self.cfg, githubRespaldoRepo="u/r")
        with mock.patch.object(espejo_github.credenciales, "leer", return_value="t" * 40), \
             mock.patch.object(espejo_github, "_api", return_value=(200, {"private": False, "full_name": "u/r"})):
            self.assertEqual(espejo_github.comprobar(cfg)["estado"], "BLOQUEADO_REPO_PUBLICO")
            self.assertEqual(espejo_github.sincronizar(cfg)["estado"], "BLOQUEADO_REPO_PUBLICO")
    def test_sha_de_blob_como_git(self):
        self.assertEqual(espejo_github._blob_sha(b"hola\n"), "5c1b14949828006ed75a3e8858957f86a2f7e2eb")

class Instrucciones(Base):
    def test_versiones_con_nombre_y_fecha(self):
        (self.r / "01-INSTRUCCIONES").mkdir(exist_ok=True)
        (self.r / "01-INSTRUCCIONES/BOOTSTRAP-CHATGPT-CLAUDE-R5.txt").write_text("arranque viejo r5", "utf-8")
        l = instrucciones.listar(self.cfg)["instrucciones"]
        self.assertEqual([(i["version"], i["estado"]) for i in l], [(5, "VIGENTE")])
        n = instrucciones.nueva_version(self.cfg, "TCSA", "arranque", "Arranque TCSA3000 (cualquier IA)", "texto nuevo del arranque con MCP principal", "MCP principal")
        self.assertRegex(n["nueva"]["archivo"], r"01-INSTRUCCIONES/TCSA - Arranque TCSA3000 \(cualquier IA\) - v6 \(\d{4}-\d{2}-\d{2}\)\.txt")
        l = {i["version"]: i["estado"] for i in instrucciones.listar(self.cfg)["instrucciones"]}
        self.assertEqual(l, {6: "VIGENTE", 5: "SUSTITUIDA"})
        self.assertIn("MCP principal", instrucciones.vigente("TCSA", "arranque", self.cfg)["texto"])
        self.assertTrue((self.r / "01-INSTRUCCIONES/BOOTSTRAP-CHATGPT-CLAUDE-R5.txt").is_file())

class AdaptadorUTF8(Base):
    def test_stdio_respeta_utf8_y_no_degrada_ante_error_http(self):
        msg = {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "tcsa3000_menu", "arguments": {"agente": "prueba ñ €"}}}
        env = dict(os.environ, TCSA3000_HOME=str(self.home), PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="cp1252", PYTHONUTF8="0")
        p = subprocess.run([sys.executable, "-B", str(REPO / "tcsa3000" / "mcp_stdio.py")], input=(json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"),
                           capture_output=True, env=env, timeout=60)
        out = json.loads(p.stdout.decode("utf-8").splitlines()[0])
        self.assertEqual(out["id"], 7, p.stderr.decode("utf-8", "replace"))

if __name__ == "__main__":
    unittest.main(verbosity=2)

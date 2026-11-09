"""R007: propuestas de trabajo (maestro v1.5.0 s.19) - aceptar = ejecutar en un bloque."""
import sys, unittest
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
_m = sys.modules.get("tcsa3000")
if _m is not None and not hasattr(_m, "__path__"):
    del sys.modules["tcsa3000"]
from tcsa3000 import propuestas as PR, tools, continuidad as C
from tests.test_r003 import Base


class Propuestas(Base):
    def test_ciclo_completo_y_reglas(self):
        p = PR.crear(self.cfg, "AF-CORE", "Instalar Docker", "Aislar agentes", ["wsl --install", "Docker Desktop"],
                     ["Descarga Docker Desktop", "UAC"], "RAM", "motor listo", "Claude")
        self.assertEqual((p["id"], p["estado"]), ("PROP-001", "PROPUESTA"))
        with self.assertRaises(ValueError):
            PR.cambiar(self.cfg, "PROP-001", "TERMINADA", evidencias=["x"])  # salto prohibido
        with self.assertRaises(ValueError):
            PR.cambiar(self.cfg, "PROP-001", "ACEPTADA")  # falta quien
        a = PR.cambiar(self.cfg, "PROP-001", "ACEPTADA", quien="usuario")
        self.assertEqual(a["aceptacion"]["cubre"]["efectos"], ["Descarga Docker Desktop", "UAC"])
        PR.cambiar(self.cfg, "PROP-001", "EN_EJECUCION", quien="Claude")
        with self.assertRaises(ValueError):
            PR.cambiar(self.cfg, "PROP-001", "TERMINADA", quien="Claude")  # sin evidencias
        t = PR.cambiar(self.cfg, "PROP-001", "TERMINADA", quien="Claude", evidencias=["motorListo=true"])
        self.assertEqual(t["estado"], "TERMINADA")
        root = C.root(self.cfg) / "11-PROPUESTAS"
        self.assertTrue((root / "PROP-001.md").is_file() and (root / "INDEX.json").is_file())
        self.assertEqual(PR.crear(self.cfg, "AF-CORE", "Otra", "x")["id"], "PROP-002")

    def test_por_mcp(self):
        r = tools.handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "tcsa3000_propuesta_crear",
              "arguments": {"projectId": "AF-CORE", "titulo": "Prueba MCP", "objetivo": "o", "pasos": ["a"], "efectos": []}}}, self.cfg)
        self.assertFalse(r["result"]["isError"], r)
        names = {t["name"] for t in tools.lista_para("REMOTO_LECTURA")}
        self.assertIn("tcsa3000_propuestas", names)
        r = tools.handle_jsonrpc({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "tcsa3000_propuesta_estado",
              "arguments": {"id": "PROP-001", "estado": "ACEPTADA", "quien": "usuario"}}}, self.cfg, "REMOTO_LECTURA")
        self.assertTrue(r["result"]["isError"])  # en solo lectura no se escribe


if __name__ == "__main__":
    unittest.main()

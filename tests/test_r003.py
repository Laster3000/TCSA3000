"""R003: paridad con TCSA (reanudar, cierres C0-C3, operaciones, proyectos nuevos, LISTA/DESCUBRIMIENTOS, conversaciones,
sync, enrutador, lista antigua) y aislamiento entre proyectos. Usa las herramientas REALES del TCSA (copiadas en fixtures)."""
import gzip, hashlib, json, os, shutil, sys, tempfile, unittest, zipfile
from pathlib import Path
from unittest import mock
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
_m = sys.modules.get("tcsa3000")
if _m is not None and not hasattr(_m, "__path__"):
    del sys.modules["tcsa3000"]
from tcsa3000 import config, continuidad as C, legado, tools
from tests.test_r002 import fixture_tcsa

HERR = REPO / "tests" / "fixtures" / "tcsa_herramientas"

def ampliar_fixture(root: Path):
    (root / "00-CHECKPOINTS").mkdir(exist_ok=True); (root / "06-EXPORT-PUBLICO/tools").mkdir(parents=True)
    shutil.copy2(HERR / "REANUDAR-PROYECTO.py", root / "00-CHECKPOINTS")
    for f in ("route_work.py", "archive_search.py"): shutil.copy2(HERR / f, root / "06-EXPORT-PUBLICO/tools")
    m = (root / "INSTRUCCIONES-MAESTRAS.md").read_bytes()
    (root / "MANIFEST-INSTRUCCIONES.json").write_text(json.dumps({"version": "1.2.0", "sha256": hashlib.sha256(m).hexdigest()}), "utf-8")
    (root / "LEEME-PRIMERO.md").write_text("# LEEME\nindice ligero", "utf-8")
    h = root / "09-HISTORICO/LISTA-ANTIGUA-MMC"; h.mkdir(parents=True)
    with gzip.open(root / "09-HISTORICO/CATALOGO-FICHEROS-LEGADO.jsonl.gz", "wt", encoding="utf-8") as f:
        f.write(json.dumps({"path": "C:/MMC/motor/idea-vieja.md", "size": 10}) + "\n")
    moji = "Autorización de prueba".encode("utf-8").decode("cp1252").encode("utf-8").decode("cp1252")  # doble mojibake real
    with zipfile.ZipFile(h / "LISTA-ORIGINAL-ARCHIVO.zip", "w") as z:
        z.writestr("LISTA/idea-vieja.md", "idea vieja")
        z.writestr("INDEX.json", json.dumps({"retrieval": {"notes": [{"memoryKey": "LISTA-001", "title": moji, "category": "x"},
                                                                   {"memoryKey": "LISTA-002", "title": "segunda nota", "category": "y"}]}}))
        z.writestr("ITEMS/LISTA-001-PRUEBA.md", "# LISTA-001\ncontenido viejo")
    (root / "07-LISTA/LISTA-TCSA-001.md").write_text("# LISTA-TCSA-001\n", "utf-8")
    c = json.loads((root / "02-CATALOGO/PROYECTOS.json").read_text("utf-8"))
    c["projects"][1] = {"projectId": "AF-CORE", "name": "AUTOFABRICADOR", "status": "CANDIDATE", "capsule": "03-PROYECTOS/AF-CORE/CAPSULA-PROYECTO.json"}
    c["projects"].append({"projectId": "TCSA-CORE", "name": "TCSA", "status": "DOC_OPERATIVA", "capsule": "03-PROYECTOS/TCSA-CORE/CAPSULA-PROYECTO.json",
                          "continuityIndex": "03-PROYECTOS/TCSA-CORE/REANUDACION-INDEX-R2.json"})
    (root / "02-CATALOGO/PROYECTOS.json").write_text(json.dumps(c), "utf-8")
    (root / "03-PROYECTOS/AF-CORE").mkdir(parents=True); (root / "03-PROYECTOS/TCSA-CORE").mkdir(parents=True)
    (root / "03-PROYECTOS/AF-CORE/CAPSULA-PROYECTO.json").write_text(json.dumps({"projectId": "AF-CORE", "revisionId": "AF-R005", "nextAction": "R006"}), "utf-8")
    (root / "03-PROYECTOS/TCSA-CORE/CAPSULA-PROYECTO.json").write_text(json.dumps({"projectId": "TCSA-CORE", "revisionId": "R2"}), "utf-8")
    cp = C._nuevo_checkpoint(root, "TCSA-CORE", None, {"revisionId": "R2", "status": "DOC_OPERATIVA", "resumen": "inicial"}, [], "seguir")
    (root / "03-PROYECTOS/TCSA-CORE/REANUDACION-INDEX-R2.json").write_text(json.dumps({"projectId": "TCSA-CORE", "latestProjectCheckpointPointer": "00-CHECKPOINTS/BY-PROJECT/TCSA-CORE/LATEST.json",
        "newCheckpointSha256": cp["checkpointSha256"], "conversationCheckpoints": [], "nextAction": "seguir"}), "utf-8")

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()); self.home = self.tmp / "TCSA3000"; self.home.mkdir()
        shutil.copy2(REPO / "NORMAS-TCSA3000.md", self.home)
        self.r = self.tmp / "TCSA"; fixture_tcsa(self.r); ampliar_fixture(self.r)
        self.env = mock.patch.dict(os.environ, {"TCSA3000_HOME": str(self.home)}); self.env.start()
        (self.home / "tcsa3000.config.json").write_text(json.dumps({"tcsaRoot": str(self.r), "fallbackDir": str(self.r / "x/y"), "respaldoDir": str(self.tmp / "DRIVE" / "TCSA")}), "utf-8")
        self.cfg = config.load(); legado._cache.clear()
    def tearDown(self):
        self.env.stop(); shutil.rmtree(self.tmp, ignore_errors=True)
    def cat(self):
        return {p["projectId"]: p for p in json.loads((self.r / "02-CATALOGO/PROYECTOS.json").read_text("utf-8"))["projects"]}

class Arranque(Base):
    def test_arranque_verifica_maestro_y_menu(self):
        a = C.arranque(self.cfg)
        self.assertEqual(a["maestro"]["estado"], "VERIFICADO"); self.assertIn("LEEME", a["leemePrimero"])
        self.assertEqual({p["projectId"] for p in a["menu"]["proyectos"]}, {"TCSA3000", "AF-CORE", "TCSA-CORE"})
    def test_maestro_alterado_se_detecta(self):
        (self.r / "INSTRUCCIONES-MAESTRAS.md").write_text("cambiado", "utf-8")
        self.assertIn("DISCREPANCIA", C.verificar_maestro(self.r)["estado"])

class Proyectos(Base):
    def test_crear_proyecto_aislado_y_reanudable(self):
        af_before = (self.r / "03-PROYECTOS/AF-CORE/CAPSULA-PROYECTO.json").read_bytes(); cat_before = self.cat()
        r = C.crear_proyecto(self.cfg, "MI-APP", "Mi app", "Probar continuidad", "P1", "D:/MI-APP", "", "test")
        self.assertEqual(r["estado"], C.PENDIENTE)
        cat = self.cat(); self.assertEqual(cat["MI-APP"]["status"], "PROPUESTO")
        for k in ("TCSA3000", "AF-CORE", "TCSA-CORE"): self.assertEqual(cat[k], cat_before[k])
        self.assertEqual((self.r / "03-PROYECTOS/AF-CORE/CAPSULA-PROYECTO.json").read_bytes(), af_before)
        z = C.reanudar(self.cfg, "MI-APP")
        self.assertEqual(z["cadenaCheckpoints"]["entradas"], 1); self.assertEqual(z["cadenaCheckpoints"]["operacionesSinCommit"], [])
        self.assertEqual(len(z["cadenaCheckpoints"]["operacionesHechasNoRepetir"]), 1)
        with self.assertRaises(FileExistsError): C.crear_proyecto(self.cfg, "MI-APP", "x", "y")
        with self.assertRaises(ValueError): C.crear_proyecto(self.cfg, "../X", "x", "y")
        self.assertTrue(any((self.r / "99-RECUPERACION/TCSA3000").rglob("PROYECTOS.json")))

class Cierres(Base):
    def test_c0_c1_c2_c3(self):
        self.assertEqual(C.cierre(self.cfg, "AF-CORE", "C0", "consulta", next_action="x")["estado"], "SIN_ESCRITURA")
        self.assertIn("BLOQUEADO", C.cierre(self.cfg, "AF-CORE", "C3", "migrar", next_action="x")["estado"])
        c1 = C.cierre(self.cfg, "AF-CORE", "C1", "cambio pequeno", "ok", ["t1 PASS"], [], [], "seguir R006")
        self.assertTrue((self.r / c1["ruta"]).is_file()); self.assertNotIn("checkpoint", c1)
        cap_before = json.loads((self.r / "03-PROYECTOS/TCSA3000/CAPSULA-PROYECTO.json").read_text("utf-8"))
        c2 = C.cierre(self.cfg, "AF-CORE", "C2", "integracion", "PASS", next_action="R007", revision_id="AF-R006")
        self.assertIn("checkpoint", c2)
        cap = json.loads((self.r / "03-PROYECTOS/AF-CORE/CAPSULA-PROYECTO.json").read_text("utf-8"))
        self.assertEqual((cap["nextAction"], cap["revisionId"]), ("R007", "AF-R006"))
        self.assertEqual(self.cat()["AF-CORE"]["nextAction"], "R007"); self.assertNotEqual(self.cat()["TCSA3000"].get("nextAction"), "R007")
        self.assertEqual(json.loads((self.r / "03-PROYECTOS/TCSA3000/CAPSULA-PROYECTO.json").read_text("utf-8")), cap_before)
        c2b = C.cierre(self.cfg, "AF-CORE", "C2", "otra", next_action="R008")
        z = C.reanudar(self.cfg, "AF-CORE")["cadenaCheckpoints"]
        self.assertEqual(z["entradas"], 2); self.assertEqual(z["checkpointId"], c2b["checkpoint"]["checkpointId"])
        with self.assertRaises(ValueError): C.cierre(self.cfg, "AF-CORE", "C1", "", next_action="")
    def test_c2_tcsa_core_mantiene_valida_la_herramienta_original(self):
        C.cierre(self.cfg, "TCSA-CORE", "C2", "mejora", next_action="siguiente")
        r = legado.reanudador(self.cfg).retrieve("TCSA-CORE")
        self.assertEqual(r["checkpointChainEntries"], 2); self.assertEqual(r["nextAction"], "siguiente"); self.assertEqual(r["operationIntentsWithoutValidCommit"], [])

class Leases(Base):
    def test_un_agente_a_la_vez(self):
        a = C.abrir_proyecto(self.cfg, "AF-CORE", "Claude"); tok = a["lease"]["token"]
        self.assertEqual(C.abrir_proyecto(self.cfg, "AF-CORE", "ChatGPT")["estado"], "PROYECTO_EN_USO")
        with self.assertRaises(PermissionError): C.cierre(self.cfg, "AF-CORE", "C1", "x", next_action="y", agente="ChatGPT")
        C.cierre(self.cfg, "AF-CORE", "C1", "x", next_action="y", agente="Claude", lease=tok)
        C.cierre(self.cfg, "TCSA3000", "C1", "otro proyecto libre", next_action="y", agente="ChatGPT")
        C.cerrar_proyecto(self.cfg, "AF-CORE", tok)
        self.assertIn("lease", C.abrir_proyecto(self.cfg, "AF-CORE", "ChatGPT"))

class Operaciones(Base):
    def test_intent_commit_no_replay(self):
        C.operacion(self.cfg, "AF-CORE", "OP-1", "INTENT", {"accion": "build"})
        self.assertEqual(C.operacion(self.cfg, "AF-CORE", "OP-1", "INTENT")["estado"], "YA_EXISTE_INTENT_NO_REPETIR")
        C.cierre(self.cfg, "AF-CORE", "C2", "base", next_action="x")
        self.assertIn("OP-1", json.dumps(C.reanudar(self.cfg, "AF-CORE")["cadenaCheckpoints"]["operacionesSinCommit"]))
        C.operacion(self.cfg, "AF-CORE", "OP-1", "COMMIT", estado="SUCCEEDED")
        self.assertEqual(C.operacion(self.cfg, "AF-CORE", "OP-1", "COMMIT")["estado"], "YA_CONFIRMADA_NO_REPETIR")
        with self.assertRaises(LookupError): C.operacion(self.cfg, "AF-CORE", "OP-2", "COMMIT")

class ListaDesc(Base):
    def test_lista_guardar_duplicado_ampliar(self):
        g = C.lista_guardar(self.cfg, "Menu de bandeja mas claro", "TCSA3000", "El usuario lo pidio")
        self.assertEqual(g["guardado"]["id"], "LISTA-TCSA-002"); self.assertTrue((self.r / "07-LISTA/LISTA-TCSA-002.md").is_file())
        self.assertEqual(C.lista_guardar(self.cfg, "Menu de bandeja mas claro y bonito", "TCSA3000", "x")["estado"], "POSIBLE_DUPLICADO_NO_GUARDADO")
        C.lista_ampliar(self.cfg, "LISTA-TCSA-002", "hecho en R003", "CONSTRUIDO", "test")
        self.assertIn("hecho en R003", (self.r / "07-LISTA/LISTA-TCSA-002.md").read_text("utf-8"))
        self.assertEqual(C.lista_ampliar(self.cfg, "LISTA-TCSA-001", "nota", agente="t")["registro"]["status"], "PROPUESTO")
        with self.assertRaises(ValueError): C.lista_ampliar(self.cfg, "LISTA-TCSA-002", "x", "INVENTADO")
    def test_descubrimiento_guardar_y_actualizar(self):
        with self.assertRaisesRegex(ValueError, "SOLO_IMPORTANTE"):
            C.desc_guardar(self.cfg, "Arreglo menor de un import", "ERROR", ["TCSA3000"], "detalle pequeno ya resuelto")
        g = C.desc_guardar(self.cfg, "La continuidad canonica vive en TCSA3000", "DECISION", ["TCSA3000"], "Drive pasa a ser espejo",
                           estado="PROBADO", impacto="CRITICO", porque_importa="Cambia donde leen y escriben todas las IAs: 100% de la continuidad")
        self.assertEqual(g["guardado"]["discoveryId"], "DESC-003")
        C.desc_actualizar(self.cfg, "DESC-003", "confirmado en Windows", "PROBADO")
        r = C.desc_retirar(self.cfg, "DESC-003", "prueba de retirada controlada")
        self.assertNotIn("DESC-003", (self.r / "08-DESCUBRIMIENTOS/INDEX.json").read_text("utf-8"))
        self.assertIn("DESC-003", (self.r / "08-DESCUBRIMIENTOS/RETIRADOS.json").read_text("utf-8"))
        self.assertTrue((self.r / "08-DESCUBRIMIENTOS/RETIRADOS/DESC-003.md").is_file())
        g2 = C.desc_guardar(self.cfg, "Otro descubrimiento distinto y relevante", "RIESGO", ["AF-CORE"], "x", impacto="ALTO", porque_importa="Evita perder trabajo al reanudar")
        self.assertEqual(g2["guardado"]["discoveryId"], "DESC-004")  # el ID retirado no se reutiliza
        with self.assertRaises(LookupError): C.desc_guardar(self.cfg, "x" * 5, "T", ["NOEXISTE"], "y", impacto="ALTO", porque_importa="z" * 30)
    def test_lista_antigua_solo_historico(self):
        r = C.lista_antigua(self.cfg, "idea-vieja"); self.assertIn("NO VIGENTE", r["aviso"]); self.assertTrue(r["resultados"])
    def test_lista_antigua_visible_y_reparada(self):
        v = C.lista_antigua_ver(self.cfg)
        self.assertEqual(v["total"], 2); self.assertEqual(v["notas"][0]["titulo"], "Autorización de prueba")
        f = C.lista_antigua_ficha(self.cfg, "LISTA-001"); self.assertIn("contenido viejo", f["texto"]); self.assertIn("NO VIGENTE", f["aviso"])
        self.assertEqual(len(C.lista_antigua_ver(self.cfg, "segunda")["notas"]), 1)

class Seguridad(Base):
    def test_rutas_y_solo_lectura(self):
        with self.assertRaises(ValueError): C.leer(self.cfg, "../fuera.txt")
        with self.assertRaises(PermissionError): C.leer(self.cfg, "09-HISTORICO/CATALOGO-FICHEROS-LEGADO.jsonl.gz")
        p = self.r / "INSTRUCCIONES-MAESTRAS.md"
        with self.assertRaises(PermissionError): C._cas(self.r, p, p.read_bytes(), b"x", "OP")
        self.assertIn("texto", C.documento(self.cfg, "leeme"))
    def test_escritura_bloqueada_en_modo_degradado(self):
        with self.assertRaises(PermissionError): tools.call("tcsa3000_lista_guardar", {"titulo": "abc", "projectId": "TCSA3000", "motivo": "m"}, self.cfg, "DEGRADADO_SIN_SERVICIO")
        self.assertIn("proyectos", tools.call("tcsa3000_menu", {}, self.cfg, "DEGRADADO_SIN_SERVICIO"))
    def test_cas_detecta_otro_escritor(self):
        p = self.r / "07-LISTA/INDEX.json"; old = p.read_bytes(); p.write_bytes(old + b" ")
        with self.assertRaises(RuntimeError): C._cas(self.r, p, old, b"{}", "OP")

class Otros(Base):
    def test_conversacion_sync_enrutar(self):
        g = C.guardar_conversacion(self.cfg, "TCSA3000", "LOCAL-T1", "Claude", [{"rol": "usuario", "texto": "hola", "cobertura": "LITERAL"}])
        f = self.r / g["ruta"]; self.assertIn("NOT_FULL_TRANSCRIPT", f.read_text("utf-8"))
        self.assertEqual(C.confirmar_sync(self.cfg, g["ruta"], "id1", f.stat().st_size)["estado"], "SYNC_VERIFIED")
        self.assertEqual(C.confirmar_sync(self.cfg, g["ruta"], "id1", 1)["estado"], "SYNC_MISMATCH")
        self.assertEqual(C.enrutar(self.cfg, {"kind": "test"})["route"], "L0_DETERMINISTIC")
        with self.assertRaises(ValueError): C.guardar_conversacion(self.cfg, "TCSA3000", "LOCAL-T1", "x", [{"texto": "a", "cobertura": "FULL"}])

class Espejo(Base):
    def test_espejo_sube_importa_conflicto_y_nunca_borra(self):
        from tcsa3000 import espejo
        (self.tmp / "DRIVE").mkdir()
        r = espejo.sincronizar(self.cfg); self.assertEqual(r["estado"], "OK"); self.assertGreater(r["subidosADrive"], 10)
        d = Path(self.cfg["respaldoDir"])
        self.assertEqual(espejo.verificar(self.cfg)["distintos"], [])
        (d / "00-CHECKPOINTS/BY-PROJECT/AF-CORE/CIERRES").mkdir(parents=True)
        (d / "00-CHECKPOINTS/BY-PROJECT/AF-CORE/CIERRES/web.json").write_text("{}", "utf-8")  # cierre de una IA web en Drive
        (self.r / "LEEME-PRIMERO.md").write_text("cambio local", "utf-8"); (d / "LEEME-PRIMERO.md").write_text("cambio en drive", "utf-8")
        (self.r / "07-LISTA/README-borrado.md").write_text("x", "utf-8"); espejo.sincronizar(self.cfg)
        os.remove(self.r / "07-LISTA/README-borrado.md")
        r = espejo.sincronizar(self.cfg)
        self.assertTrue((self.r / "00-CHECKPOINTS/BY-PROJECT/AF-CORE/CIERRES/web.json").is_file())
        self.assertEqual((d / "LEEME-PRIMERO.md").read_text("utf-8"), "cambio local")
        self.assertTrue(any((self.r / "99-RECUPERACION/TCSA3000/CONFLICTOS-DRIVE").rglob("LEEME-PRIMERO.md")))
        self.assertTrue((d / "07-LISTA/README-borrado.md").is_file()); self.assertFalse((self.r / "07-LISTA/README-borrado.md").exists())
    def test_sin_unidad_de_respaldo(self):
        from tcsa3000 import espejo
        cfg = dict(self.cfg, respaldoDir=str(self.tmp / "NOHAY" / "X" / "TCSA"))
        self.assertEqual(espejo.sincronizar(cfg)["estado"], "BLOQUEADO")

class Remoto(Base):
    def test_modo_remoto_solo_lectura_y_search_fetch(self):
        names = {t["name"] for t in tools.lista_para("REMOTO_LECTURA")}
        self.assertIn("search", names); self.assertIn("fetch", names); self.assertNotIn("tcsa3000_cierre", names)
        with self.assertRaisesRegex(PermissionError, "REMOTA"): tools.call("tcsa3000_cierre", {"projectId": "AF-CORE", "nivel": "C1", "resumen": "x", "nextAction": "y"}, self.cfg, "REMOTO_LECTURA")
        tools.call("tcsa3000_cierre", {"projectId": "AF-CORE", "nivel": "C1", "resumen": "x", "nextAction": "y"}, self.cfg, "REMOTO_ESCRITURA")
        from tcsa3000 import index
        index.reindex(self.cfg)
        s = tools.call("search", {"query": "economia"}, self.cfg, "REMOTO_LECTURA"); self.assertTrue(s["results"])
        f = tools.call("fetch", {"id": s["results"][0]["id"]}, self.cfg, "REMOTO_LECTURA"); self.assertTrue(f["text"])
        self.assertNotIn("search", {t["name"] for t in tools.lista_para("SERVICIO")})

if __name__ == "__main__":
    unittest.main(verbosity=2)

"""R008: el servicio vive solo con TCSA3000.exe abierto."""
import json, os, subprocess, sys, unittest
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
_m = sys.modules.get("tcsa3000")
if _m is not None and not hasattr(_m, "__path__"):
    del sys.modules["tcsa3000"]
from tcsa3000 import bandeja, config
from tests.test_r003 import Base


class Bandeja(Base):
    def test_viva_atado(self):
        os.environ.pop("TCSA3000_SIN_BANDEJA", None)
        self.assertTrue(bandeja.atado({}))
        self.assertFalse(bandeja.atado({"atadoABandeja": False}))
        f = config.data_dir() / "bandeja.json"
        f.unlink(missing_ok=True)
        self.assertFalse(bandeja.viva())
        p = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(20)"])
        f.write_text(json.dumps({"pid": p.pid, "exe": Path(sys.executable).name}))
        self.assertTrue(bandeja.viva())
        p.kill(); p.wait()
        self.assertFalse(bandeja.viva())


if __name__ == "__main__":
    unittest.main()

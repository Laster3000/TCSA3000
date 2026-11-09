"""Ejecuta las regresiones del tunel en interprete aislado.

Otros tests del repositorio incluyen src/tcsa3000.py como modulo independiente,
que sombrearia el paquete tcsa3000 dentro del mismo proceso de descubrimiento.
"""
import subprocess
import sys
import unittest
from pathlib import Path


class SecureTunnelRegressionSuite(unittest.TestCase):
    def test_regresiones_en_interprete_aislado(self):
        root = Path(__file__).resolve().parents[1]
        run = subprocess.run(
            [sys.executable, "-B", "-m", "unittest",
             "tests.regression_openai_tunnel", "-v"],
            cwd=str(root), capture_output=True, text=True, timeout=35,
            check=False,
        )
        self.assertEqual(run.returncode, 0, run.stdout + "\n" + run.stderr)
        self.assertIn("Ran 3 tests", run.stderr)


if __name__ == "__main__":
    unittest.main()

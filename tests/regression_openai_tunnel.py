"""Regresiones del Secure MCP Tunnel: Windows UTF-8 y modo stdio privado."""
import json
import unittest
from pathlib import Path
from unittest import mock

from tcsa3000 import mcp_stdio, openai_tunel


class OpenAITunnelRegressionTests(unittest.TestCase):
    def test_windows_console_encoding_risk(self):
        # UTF-8 de un simbolo usado por tunnel-client incluye 0x90,
        # que Windows cp1252 no puede decodificar.
        utf8 = bytes.fromhex("f09f8c90")
        with self.assertRaises(UnicodeDecodeError):
            utf8.decode("cp1252")
        self.assertEqual(ord(utf8.decode("utf-8")), 0x1F310)

    def test_spawn_drains_utf8_stdout_and_uses_private_stdio(self):
        cfg = {"port": 18730, "openaiTunnelId": "tunnel_" + "a" * 32}
        proc = mock.MagicMock()
        proc.poll.return_value = None
        old_proc = openai_tunel._proc
        old_health = openai_tunel._health
        self.addCleanup(setattr, openai_tunel, "_proc", old_proc)
        self.addCleanup(setattr, openai_tunel, "_health", old_health)
        openai_tunel._proc = None
        with mock.patch.object(openai_tunel, "exe", return_value=Path(__file__)), \
             mock.patch.object(openai_tunel.credenciales, "leer", return_value="TEST_RUNTIME_KEY_NOT_REAL"), \
             mock.patch.object(openai_tunel.config, "python_exe", return_value=r"D:\TCSA3000\runtime\python.exe"), \
             mock.patch.object(openai_tunel, "_puerto_libre", return_value=51000), \
             mock.patch.object(openai_tunel, "_listo", return_value=True), \
             mock.patch.object(openai_tunel, "estado", return_value={"listo": True, "enMarcha": True}), \
             mock.patch.object(openai_tunel, "journal"), \
             mock.patch.object(openai_tunel.time, "sleep"), \
             mock.patch.object(openai_tunel.threading, "Thread"), \
             mock.patch.object(openai_tunel.subprocess, "Popen", return_value=proc) as popen:
            result = openai_tunel.iniciar(cfg)
        self.assertTrue(result["listo"])
        argv = popen.call_args.args[0]
        options = popen.call_args.kwargs
        self.assertEqual(options["encoding"], "utf-8")
        self.assertEqual(options["errors"], "replace")
        self.assertEqual(options["bufsize"], 1)
        self.assertIn("--mcp.command", argv)
        self.assertIn("--openai", argv[argv.index("--mcp.command") + 1])
        self.assertIn("D:/TCSA3000/runtime/python.exe", argv[argv.index("--mcp.command") + 1])

    def test_openai_stdio_uses_remote_permission_gate(self):
        payload = {"jsonrpc": "2.0", "id": 5, "result": {}}
        class Reply:
            def __enter__(self): return self
            def __exit__(self, *exc): return False
            def read(self): return json.dumps(payload).encode("utf-8")

        msg = {"jsonrpc": "2.0", "id": 5, "method": "ping"}
        with mock.patch.object(mcp_stdio.openai_tunel, "secreto", return_value="LOCAL_TEST_ONLY"), \
             mock.patch.object(mcp_stdio.urllib.request, "urlopen", return_value=Reply()) as get:
            got = mcp_stdio.forward({"port": 18730}, "UNUSED_TOKEN", msg, "openai")
        self.assertEqual(got, payload)
        request = get.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:18730/openai/LOCAL_TEST_ONLY/mcp")
        self.assertNotIn("X-tcsa3000-token", {k.lower() for k in request.headers})


if __name__ == "__main__":
    unittest.main()

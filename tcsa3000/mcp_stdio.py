"""Adaptador MCP stdio de TCSA3000 (lo lanza el cliente: Claude Desktop, Codex...).
Reenvia al servicio local. Si el servicio no responde, sigue en MODO_DEGRADADO (lectura directa) e indica el respaldo en Drive."""
from __future__ import annotations
import json, sys, urllib.request
from pathlib import Path
if __package__ in (None, ""):
    _aqui = str(Path(__file__).resolve().parent)
    sys.path[:] = [x for x in sys.path if str(Path(x or ".").resolve()) != _aqui]  # evita sombrear la stdlib
    sys.path.insert(0, str(Path(__file__).resolve().parents[1])); __package__ = "tcsa3000"
from tcsa3000 import config, credenciales, tools

AVISO = ("SERVICIO_TCSA3000_NO_RESPONDE: respuesta en MODO_DEGRADADO (lectura directa). Arranca o reinicia TCSA3000 desde la bandeja. "
         "Respaldo para cualquier IA: Drive TCSA/03-PROYECTOS/TCSA3000/ESTADO-FALLBACK/CONTEXTO-TCSA3000.md")

def forward(cfg, token, msg):
    req = urllib.request.Request("http://127.0.0.1:%d/mcp" % cfg["port"], json.dumps(msg).encode("utf-8"),
                                 {"Content-Type": "application/json", "X-TCSA3000-Token": token})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    return json.loads(body) if body else None

def main():
    cfg = config.load()
    try: token = credenciales.token_servicio()
    except OSError: token = ""
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try: msg = json.loads(line)
        except ValueError:
            out = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            try:
                out = forward(cfg, token, msg)
            except Exception:
                out = tools.handle_jsonrpc(msg, cfg, modo="DEGRADADO_SIN_SERVICIO")
                if out and msg.get("method") == "tools/call" and "result" in out:
                    out["result"]["content"].insert(0, {"type": "text", "text": AVISO})
        if out is not None:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n"); sys.stdout.flush()

if __name__ == "__main__":
    main()

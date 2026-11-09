"""Adaptador MCP stdio de TCSA3000 (lo lanza el cliente: Claude Desktop, Codex...).
Reenvia al servicio local. Si el servicio no responde, sigue en MODO_DEGRADADO (lectura directa) e indica el respaldo en Drive."""
from __future__ import annotations
import io, json, sys, urllib.error, urllib.request
from pathlib import Path
if __package__ in (None, ""):
    _aqui = str(Path(__file__).resolve().parent)
    sys.path[:] = [x for x in sys.path if str(Path(x or ".").resolve()) != _aqui]  # evita sombrear la stdlib
    sys.path.insert(0, str(Path(__file__).resolve().parents[1])); __package__ = "tcsa3000"
from tcsa3000 import config, conexiones, credenciales, openai_tunel, tools

AVISO = ("SERVICIO_TCSA3000_NO_RESPONDE: respuesta en MODO_DEGRADADO (lectura directa). Arranca o reinicia TCSA3000 desde la bandeja. "
         "Respaldo para cualquier IA: Drive TCSA/03-PROYECTOS/TCSA3000/ESTADO-FALLBACK/CONTEXTO-TCSA3000.md")

def forward(cfg, token, msg, canal="local"):
    # El canal OpenAI usa la ruta privada del tunel seguro: respeta openaiEscritura.
    # No pasa por /mcp (SERVICIO), que permitiria escritura aun con el interruptor desactivado.
    if canal.startswith("cx:"):
        cid = canal[3:]; c = conexiones.obtener(cid)
        destino = conexiones.ruta_local(cfg, cid)
        cabeceras = {"Content-Type": "application/json"}
        if c.get("auth") == "token":
            cabeceras["Authorization"] = "Bearer " + (credenciales.leer("tcsa3000-token-" + cid) or "")
    elif canal == "openai":
        destino = "http://127.0.0.1:%d/openai/%s/mcp" % (cfg["port"], openai_tunel.secreto())
        cabeceras = {"Content-Type": "application/json"}
    else:
        destino = "http://127.0.0.1:%d/mcp" % cfg["port"]
        cabeceras = {"Content-Type": "application/json", "X-TCSA3000-Token": token}
    req = urllib.request.Request(destino, json.dumps(msg).encode("utf-8"), cabeceras)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        # El servicio SI responde: no se cae a modo degradado (eso bloquearia la escritura en silencio).
        detalle = e.read()[:300].decode("utf-8", "replace")
        if msg.get("id") is None:
            return None
        return {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32000, "message": "SERVICIO_TCSA3000_HTTP_%d: %s" % (e.code, detalle)}}
    return json.loads(body.decode("utf-8")) if body else None

def main():
    cfg = config.load()
    argv = sys.argv[1:]
    canal = "openai" if "--openai" in argv else ("cx:" + argv[argv.index("--conexion") + 1]) if "--conexion" in argv else "local"
    try: token = credenciales.token_servicio() if canal == "local" else ""
    except OSError: token = ""
    # Windows usa cp1252 en tuberias: forzar UTF-8 de entrada y salida (las IAs envian JSON en UTF-8).
    entrada = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")
    salida = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n", write_through=True)
    for line in entrada:
        line = line.strip().lstrip("\ufeff")
        if not line: continue
        try: msg = json.loads(line)
        except ValueError:
            out = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            try:
                out = forward(cfg, token, msg, canal)
            except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
                # Solo si el servicio NO responde: lectura directa (sin escritura) + aviso del respaldo.
                out = tools.handle_jsonrpc(msg, cfg, modo="DEGRADADO_SIN_SERVICIO")
                if out and msg.get("method") == "tools/call" and "result" in out:
                    out["result"]["content"].insert(0, {"type": "text", "text": AVISO})
            except Exception as e:  # nunca matar el adaptador por un fallo puntual
                out = None if msg.get("id") is None else {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32603, "message": "ADAPTADOR: %s: %s" % (type(e).__name__, e)}}
        if out is not None:
            salida.write(json.dumps(out, ensure_ascii=False) + "\n"); salida.flush()

if __name__ == "__main__":
    main()

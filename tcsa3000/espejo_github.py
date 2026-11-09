"""Segundo respaldo: la continuidad canonica (TCSA3000/TCSA) se copia a un repositorio GitHub PRIVADO.
Orden para las IAs: 1) MCP tcsa3000  2) GitHub privado (conector de GitHub)  3) espejo de Google Drive.
- Solo repositorios PRIVADOS: si el repositorio es publico, se bloquea (la continuidad tiene datos privados).
- Un commit por sincronizacion con lo nuevo o cambiado; nunca borra nada en GitHub.
- Lo que una IA cree en GitHub y no exista aqui (p.ej. un cierre nuevo) se trae a TCSA3000.
- Token (fine-grained, solo ese repositorio, Contents: Read and write) cifrado con DPAPI: credencial github-respaldo-token."""
from __future__ import annotations
import base64, hashlib, json, os, re, urllib.error, urllib.request
from pathlib import Path
from . import config, credenciales
from .storage import utc, write_json

API = "https://api.github.com"
CRED = "github-respaldo-token"
MAX_BYTES = 45 * 1024 * 1024
IGNORAR = (".tcsa3000-stage", ".tmp-", "desktop.ini", ".~lock", "Thumbs.db", "__pycache__", ".pyc")

def _man() -> Path:
    return config.data_dir() / "github-manifiesto.json"

def _api(token: str, metodo: str, ruta: str, cuerpo=None, timeout=120):
    req = urllib.request.Request(API + ruta, json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None, method=metodo,
                                 headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                                          "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "TCSA3000", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            b = r.read(); return r.status, (json.loads(b) if b else None)
    except urllib.error.HTTPError as e:
        try: d = json.loads(e.read() or b"{}")
        except ValueError: d = {}
        return e.code, d

def _blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()

CRED_PUB = "github-publico-token"
SECRETOS = re.compile(r"(sk-[A-Za-z0-9_\-]{20,}|github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{20,}|tunnel_[a-z0-9]{32}|BEGIN [A-Z ]*PRIVATE KEY|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,})")

def token(publico: bool = False):
    return (credenciales.leer(CRED_PUB) if publico else None) or credenciales.leer(CRED)

def configurado(cfg: dict) -> bool:
    return bool(cfg.get("githubRespaldoRepo")) and credenciales.leer(CRED) is not None

def comprobar(cfg: dict) -> dict:
    repo = cfg.get("githubRespaldoRepo") or ""; tok = credenciales.leer(CRED)
    if not repo or not tok: return {"estado": "SIN_CONFIGURAR", "ayuda": "Indica el repositorio privado (usuario/nombre) y guarda el token."}
    st, d = _api(tok, "GET", "/repos/" + repo)
    if st != 200: return {"estado": "SIN_ACCESO", "http": st, "detalle": (d or {}).get("message")}
    if not d.get("private"): return {"estado": "BLOQUEADO_REPO_PUBLICO", "ayuda": "El repositorio debe ser PRIVADO: la continuidad contiene datos privados."}
    perm = (d.get("permissions") or {})
    return {"estado": "OK", "repo": d.get("full_name"), "privado": True, "puedeEscribir": bool(perm.get("push", True)), "rama": d.get("default_branch") or "main"}

def sincronizar(cfg: dict) -> dict:
    c = comprobar(cfg)
    if c["estado"] != "OK": return c
    tok = credenciales.leer(CRED); repo = c["repo"]; rama = cfg.get("githubRespaldoRama") or c["rama"]
    local = Path(cfg["tcsaRoot"]); man = json.loads(_man().read_text("utf-8")) if _man().exists() else {"ficheros": {}}
    conocidos = man.get("ficheros", {})
    st, ref = _api(tok, "GET", "/repos/%s/git/ref/heads/%s" % (repo, rama))
    if st in (404, 409):  # repositorio vacio: primer fichero por la API de contenidos
        st2, _ = _api(tok, "PUT", "/repos/%s/contents/LEEME-RESPALDO.md" % repo, {"message": "TCSA3000: inicio del respaldo", "branch": rama,
                      "content": base64.b64encode("Respaldo privado de la continuidad TCSA3000 (segundo respaldo; el principal es TCSA3000).\n".encode()).decode()})
        if st2 not in (200, 201): return {"estado": "ERROR_INICIALIZANDO", "http": st2}
        st, ref = _api(tok, "GET", "/repos/%s/git/ref/heads/%s" % (repo, rama))
    if st != 200: return {"estado": "ERROR_REF", "http": st}
    head = ref["object"]["sha"]
    st, commit = _api(tok, "GET", "/repos/%s/git/commits/%s" % (repo, head))
    st, arbol = _api(tok, "GET", "/repos/%s/git/trees/%s?recursive=1" % (repo, commit["tree"]["sha"]))
    remoto = {e["path"]: e["sha"] for e in (arbol or {}).get("tree", []) if e.get("type") == "blob"}
    entradas, subidos, omitidos, importados = [], [], [], []
    vistos = set()
    for dp, dn, fn in os.walk(local):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in fn:
            if any(x in f for x in IGNORAR): continue
            p = Path(dp) / f; rel = p.relative_to(local).as_posix(); vistos.add(rel)
            if p.stat().st_size > MAX_BYTES: omitidos.append(rel); continue
            data = p.read_bytes(); sha = _blob_sha(data)
            if remoto.get(rel) == sha: continue
            st, b = _api(tok, "POST", "/repos/%s/git/blobs" % repo, {"content": base64.b64encode(data).decode(), "encoding": "base64"}, timeout=600)
            if st != 201: return {"estado": "ERROR_SUBIENDO", "http": st, "ruta": rel}
            entradas.append({"path": rel, "mode": "100644", "type": "blob", "sha": b["sha"]}); subidos.append(rel)
    for rel, sha in remoto.items():  # nuevo en GitHub (creado por una IA) -> se trae
        if rel in vistos or rel in conocidos or rel == "LEEME-RESPALDO.md": continue
        st, b = _api(tok, "GET", "/repos/%s/git/blobs/%s" % (repo, sha))
        if st == 200:
            dst = local / rel; dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                dst.write_bytes(base64.b64decode(b["content"])); importados.append(rel)
    commit_sha = None
    if entradas:
        st, t = _api(tok, "POST", "/repos/%s/git/trees" % repo, {"base_tree": commit["tree"]["sha"], "tree": entradas}, timeout=600)
        if st != 201: return {"estado": "ERROR_ARBOL", "http": st}
        st, nc = _api(tok, "POST", "/repos/%s/git/commits" % repo, {"message": "TCSA3000: respaldo %s (%d ficheros)" % (utc()[:19], len(entradas)),
                                                                     "tree": t["sha"], "parents": [head]})
        if st != 201: return {"estado": "ERROR_COMMIT", "http": st}
        st, _ = _api(tok, "PATCH", "/repos/%s/git/refs/heads/%s" % (repo, rama), {"sha": nc["sha"], "force": False})
        if st != 200: return {"estado": "ERROR_REF_UPDATE", "http": st, "ayuda": "Otro escritor cambio la rama; se reintentara en el siguiente ciclo."}
        commit_sha = nc["sha"]
    write_json(_man(), {"actualizado": utc(), "repo": repo, "ficheros": {r: True for r in (vistos | set(remoto))}})
    return {"estado": "OK", "at": utc(), "repo": repo, "commit": commit_sha, "subidos": len(subidos), "importados": len(importados),
            "omitidosPorTamano": omitidos, "detalle": {"subidos": subidos[:30], "importados": importados[:30]}}


# ------------------------------------------------------------------ parte PUBLICA (solo normas e instrucciones, saneadas)
def _publicables(cfg: dict) -> dict:
    """ruta en el repositorio publico -> bytes. Solo normas e instrucciones: nunca continuidad, LISTA, checkpoints ni datos."""
    from . import instrucciones
    r = Path(cfg["tcsaRoot"]); out = {}
    for f in ("INSTRUCCIONES-MAESTRAS.md", "MANIFEST-INSTRUCCIONES.json"):
        if (r / f).is_file(): out[f] = (r / f).read_bytes()
    reg = instrucciones.listar(cfg)["instrucciones"]
    filas = ["# Instrucciones de proyecto (publicadas por TCSA3000)", "", "| Proyecto | Instrucciones | Version | Fecha | Estado | Fichero |", "|---|---|---|---|---|---|"]
    for i in reg:
        p = r / i["archivo"]
        if not p.is_file(): continue
        nombre = Path(i["archivo"]).name
        out["docs/instrucciones/" + nombre] = p.read_bytes()
        filas.append("| %s | %s | v%d | %s | %s | %s |" % (i["proyecto"], i["nombre"], i["version"], i["fecha"], i["estado"], nombre))
    out["docs/instrucciones/REGISTRO.md"] = ("\n".join(filas) + "\n").encode("utf-8")
    return out

def comprobar_publico(cfg: dict) -> dict:
    repo = cfg.get("githubPublicoRepo") or ""; tok = token(True)
    if not repo or not tok: return {"estado": "SIN_CONFIGURAR"}
    st, d = _api(tok, "GET", "/repos/" + repo)
    if st != 200: return {"estado": "SIN_ACCESO", "http": st, "detalle": (d or {}).get("message")}
    return {"estado": "OK", "repo": d.get("full_name"), "privado": bool(d.get("private")), "rama": d.get("default_branch") or "main",
            "aviso": "El repositorio es PRIVADO: lo publicado no sera visible para IAs sin acceso." if d.get("private") else None}

def publicar(cfg: dict) -> dict:
    c = comprobar_publico(cfg)
    if c["estado"] != "OK": return c
    tok = token(True); repo = c["repo"]; rama = cfg.get("githubPublicoRama") or c["rama"]
    archivos = _publicables(cfg)
    malos = [k for k, v in archivos.items() if SECRETOS.search(v.decode("utf-8", "replace"))]
    if malos: return {"estado": "BLOQUEADO_POSIBLE_SECRETO", "ficheros": malos, "ayuda": "Revisa esos ficheros: parecen contener claves, tokens, tunnel_id o correos."}
    st, ref = _api(tok, "GET", "/repos/%s/git/ref/heads/%s" % (repo, rama))
    if st != 200: return {"estado": "ERROR_REF", "http": st}
    head = ref["object"]["sha"]; st, commit = _api(tok, "GET", "/repos/%s/git/commits/%s" % (repo, head))
    st, arbol = _api(tok, "GET", "/repos/%s/git/trees/%s?recursive=1" % (repo, commit["tree"]["sha"]))
    remoto = {e["path"]: e["sha"] for e in (arbol or {}).get("tree", []) if e.get("type") == "blob"}
    entradas = []
    for ruta, data in archivos.items():
        if remoto.get(ruta) == _blob_sha(data): continue
        st, b = _api(tok, "POST", "/repos/%s/git/blobs" % repo, {"content": base64.b64encode(data).decode(), "encoding": "base64"})
        if st != 201: return {"estado": "ERROR_SUBIENDO", "http": st, "ruta": ruta}
        entradas.append({"path": ruta, "mode": "100644", "type": "blob", "sha": b["sha"]})
    if not entradas:
        return {"estado": "OK", "at": utc(), "repo": repo, "publicados": 0, "nota": "Ya estaba al dia."}
    st, t = _api(tok, "POST", "/repos/%s/git/trees" % repo, {"base_tree": commit["tree"]["sha"], "tree": entradas})
    if st != 201: return {"estado": "ERROR_ARBOL", "http": st}
    st, nc = _api(tok, "POST", "/repos/%s/git/commits" % repo, {"message": "TCSA3000: publica normas e instrucciones (%d ficheros)" % len(entradas), "tree": t["sha"], "parents": [head]})
    if st != 201: return {"estado": "ERROR_COMMIT", "http": st}
    st, _ = _api(tok, "PATCH", "/repos/%s/git/refs/heads/%s" % (repo, rama), {"sha": nc["sha"], "force": False})
    if st != 200: return {"estado": "ERROR_REF_UPDATE", "http": st}
    return {"estado": "OK", "at": utc(), "repo": repo, "commit": nc["sha"], "publicados": len(entradas), "detalle": [e["path"] for e in entradas]}

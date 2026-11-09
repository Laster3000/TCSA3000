"""Instantanea de contexto para el respaldo en Drive (si falla el puente/MCP, cualquier IA la lee por el conector de Drive)."""
from __future__ import annotations
import json
from pathlib import Path
from . import VERSION, config, continuidad, normas, sources
from .storage import atomic_write, sha_bytes, utc

def construir(cfg: dict, estado_servicio: dict | None = None) -> dict:
    snap = {"schema": "tcsa3000.fallback.v1", "generado": utc(), "version": VERSION, "ubicacion": cfg["home"],
            "aviso": "SNAPSHOT de respaldo. La continuidad canonica vive en TCSA3000 (D:\\TCSA3000\\TCSA); Drive es su espejo. No es estado vivo de ejecutores.",
            "servicio": estado_servicio or {}, "directrices": normas.leer()["texto"]}
    for k, fn in (("catalogo", lambda: sources.catalogo(cfg)), ("menu", lambda: continuidad.menu(cfg)),
                  ("maestro", lambda: continuidad.verificar_maestro(continuidad.root(cfg))), ("lista", lambda: sources.lista(cfg)),
                  ("descubrimientos", lambda: sources.descubrimientos(cfg)), ("propuestasPendientes", sources.propuestas)):
        try:
            snap[k] = fn()
        except Exception as e:  # una fuente caida no impide el respaldo del resto
            snap[k] = {"error": str(e)}
    return snap

def a_markdown(s: dict) -> str:
    L = ["# TCSA3000 - CONTEXTO DE RESPALDO", "Generado: %s | Version %s | Ubicacion: %s" % (s["generado"], s["version"], s["ubicacion"]), "", s["aviso"], "",
         "## Si eres una IA sin acceso al MCP de TCSA3000",
         "Orden de fuentes: 1) MCP tcsa3000  2) repositorio GitHub PRIVADO de respaldo (conector de GitHub)  3) este espejo de Google Drive.",
         "1. Lee INSTRUCCIONES-MAESTRAS.md y MANIFEST-INSTRUCCIONES.json (raiz TCSA) y LEEME-PRIMERO.md.",
         "2. Del proyecto pedido, lee solo su capsula (03-PROYECTOS/<ID>/CAPSULA-PROYECTO.json) y 00-CHECKPOINTS/BY-PROJECT/<ID>/LATEST.json + su checkpoint y CIERRES recientes.",
         "3. Para guardar sin MCP: crea un fichero NUEVO en 00-CHECKPOINTS/BY-PROJECT/<ID>/CIERRES/ (nunca sobrescribas indices); TCSA3000 lo vera.",
         "4. Comprueba LEASE.json del proyecto: si otro agente lo tiene activo, no escribas en ese proyecto.", ""]
    cat = s.get("catalogo", {})
    L.append("## Proyectos (catalogo TCSA)")
    for p in cat.get("proyectos", []):
        L.append("- **%s** (%s, %s) - %s" % (p.get("projectId"), p.get("priority"), p.get("status"), p.get("nextAction", "")))
    m = s.get("maestro") or {}
    L.append("\nMaestro TCSA: %s v%s" % (m.get("estado"), m.get("version")))
    L.append("\n## LISTA")
    for n in s.get("lista", {}).get("entradas", []):
        L.append("- %s [%s] %s - %s" % (n.get("id"), n.get("status"), n.get("title"), n.get("projectId")))
    L.append("\n## DESCUBRIMIENTOS")
    for r in s.get("descubrimientos", {}).get("registros", []):
        L.append("- %s [%s] %s" % (r.get("discoveryId"), r.get("status"), r.get("title")))
    L.append("\n## Propuestas pendientes de revision")
    for p in s.get("propuestasPendientes", []) if isinstance(s.get("propuestasPendientes"), list) else []:
        L.append("- %s %s (%s)" % (p.get("id"), p.get("titulo"), p.get("projectId")))
    L.append("\n## Directrices de TCSA3000\n")
    L.append(s["directrices"])
    return "\n".join(L) + "\n"

def exportar(cfg: dict, estado_servicio: dict | None = None) -> dict:
    s = construir(cfg, estado_servicio)
    d = Path(cfg["fallbackDir"])
    if not d.parent.parent.exists():
        return {"estado": "BLOQUEADO", "motivo": "CARPETA_NO_ACCESIBLE:" + str(d.parent)}
    d.mkdir(parents=True, exist_ok=True)
    j = (json.dumps(s, ensure_ascii=False, indent=1) + "\n").encode("utf-8"); m = a_markdown(s).encode("utf-8")
    atomic_write(d / "CONTEXTO-TCSA3000.json", j); atomic_write(d / "CONTEXTO-TCSA3000.md", m)
    return {"estado": "GUARDADO (se copia a Drive con el espejo)", "carpeta": str(d), "jsonSha256": sha_bytes(j), "mdSha256": sha_bytes(m), "at": s["generado"]}

# TCSA3000

TCSA3000 es el **TCSA en forma de programa**: un servidor MCP local y portátil que da a cualquier IA
(Claude Desktop, Claude Code, Codex, Cursor, Windsurf, VS Code, Gemini CLI y ChatGPT por túnel seguro) la continuidad TCSA completa.

**Dónde vive la información:** dentro de la propia carpeta de TCSA3000 (`TCSA\`). Google Drive es solo un
**espejo de respaldo** que se actualiza solo cada pocos minutos: nunca se borra nada allí, lo que una IA web cree en
Drive se trae aquí, y si algo cambió en los dos lados se guardan ambas versiones.

## Qué hace
- **Arranque**: verifica el maestro TCSA (SHA contra el manifiesto), LEEME-PRIMERO y el menú TCSA CONTROL CENTER.
- **Reanudar** un proyecto con la herramienta original `REANUDAR-PROYECTO.py` + cadena de checkpoints y operaciones sin confirmar (UNKNOWN).
- **Cierres** proporcionales del protocolo R2: C0 (nada), C1 (registro breve), C2 (checkpoint encadenado + cápsula + catálogo), C3 (bloqueado: requiere a una persona).
- **Operaciones** INTENT/COMMIT: nunca repite un SUCCEEDED.
- **Proyectos nuevos** en ámbito propio (cápsula, primer checkpoint, alta en catálogo) sin tocar los demás.
- **LISTA** y **DESCUBRIMIENTOS**: consultar, GUARDAR (con aviso de duplicados) y AMPLIAR. LISTA ANTIGUA solo bajo petición expresa.
- **Conversaciones** con cobertura etiquetada (LITERAL/CITA/RESUMEN/RECONSTRUCCION/UNKNOWN_GAP).
- **Economía P0**: enrutador `route_work` del TCSA.
- **Un agente por proyecto** (concesión LEASE); proyectos distintos pueden trabajarse a la vez.
- **Nunca borra**: los índices se cambian por CAS sobre bytes con preimagen en `99-RECUPERACION/TCSA3000/`.
- **Respaldo** automático en Drive (espejo) para IAs sin MCP o si el servicio cae (modo degradado de solo lectura).
- **ChatGPT**: túnel HTTPS de Cloudflare hacia una dirección secreta que solo expone el MCP (solo lectura por defecto;
  `cloudflared` se descarga únicamente si lo pides, de la publicación oficial, y se comprueba su firma).
- **LISTA ANTIGUA** visible entera (histórico no vigente, solo consulta).
- **DESCUBRIMIENTOS** solo para lo importante (impacto ALTO/CRÍTICO y por qué importa); lo menor se retira sin destruirse.
- **Credenciales**: inventario de dónde hay credenciales en el PC (solo nombres, nunca valores).

## Uso
Toda la carpeta es portátil (por defecto `D:\TCSA3000`).

- `TCSA3000.exe`: icono en la bandeja (sin consola) con el menú: centro de control, proyectos, LISTA, descubrimientos,
  respaldo, servicio (arrancar/parar/reiniciar), configuración (conectar IA, normas, credenciales, ubicación) y salir.
- Centro de control web local (127.0.0.1, con token): Inicio, Proyectos, LISTA, Descubrimientos, Conectar una IA,
  Normas y directrices, Credenciales, Ajustes y ubicación.
- `TCSA3000.cmd <orden>`: `estado`, `arrancar`, `parar`, `reiniciar`, `panel`, `arranque`, `menu`, `reanudar <ID>`,
  `respaldo`, `registrar-claude`, `snippet`...

Compilar la bandeja: `bandeja\compilar.cmd` (usa el `csc` de .NET Framework 4 incluido en Windows).
Runtime: `runtime\python.exe` (Python 3.12 embebido, no incluido en el repo) o el `python` del sistema.

## Garantías
- Solo escucha en `127.0.0.1`; la API exige token; `/health` no expone datos.
- Credenciales cifradas con DPAPI del usuario de Windows; nunca se muestran ni se suben.
- Normas propias versionadas con CAS, preimagen y diario encadenado.
- Sin autoarranque, servicios de Windows ni elevación.

## Pruebas
`runtime\python.exe -B -m unittest discover -s tests -t .`

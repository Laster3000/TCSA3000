# TCSA — INSTRUCCIONES MAESTRAS CANÓNICAS
Versión: 1.4.0 | Fecha: 2026-11-09 | Estado: NORMA DOCUMENTAL VIGENTE PARA CONFIGURACIÓN, NO CERTIFICACIÓN E2E
Ámbito: ChatGPT, Claude, herramientas de desarrollo y agentes autorizados que puedan leer este documento.

## 0. Qué es TCSA
TCSA es el sistema independiente de continuidad, proyectos, decisiones, descubrimientos y recuperación de trabajo de AUTOFABRICADOR y de los proyectos separados que se registren. TCSA no es el motor que genera aplicaciones: AUTOFABRICADOR lo es. Ninguna autoridad, servicio, configuración protegida, credencial ni permiso de un sistema histórico se importa al TCSA operativo.

Principios: una fuente de referencia canónica, evidencia verificable, trazabilidad, privacidad, ausencia de duplicados innecesarios y ejecución honesta. La documentación no prueba la instalación. Un checkpoint no sustituye al estado vivo de un proceso ni a los bytes de un punto de restauración.

## 0.1. REGLA SUPREMA P0 — MÍNIMO TRABAJO DE IA WEB
La IA web experta (ChatGPT/Claude) debe aportar principalmente juicio, arquitectura, diagnóstico difícil y revisión crítica. No debe consumir razonamiento remoto repitiendo inventarios, modificaciones triviales, compilaciones, pruebas, lecturas masivas o cálculos que los ejecutores deterministas y la IA local ya pueden completar con evidencia. Elegir la ruta que minimice esfuerzo total y coste sin perder calidad comprobable. Consultar las decisiones recuperables antes de pagar de nuevo por un razonamiento ya realizado. La política detallada está en `10-EFICIENCIA-IA/POLITICA-P0.md`. Esta norma no garantiza todavía un enrutador autónomo instalado.

## 1. Ubicaciones, capas y precedencia
**Repositorio público de normas y herramientas:** https://github.com/Laster3000/TCSA
**Maestro público versionado:** https://github.com/Laster3000/TCSA/blob/main/INSTRUCCIONES-MAESTRAS.md
**Continuidad canónica (desde v1.3.0): TCSA3000.** La continuidad privada vive en la carpeta `TCSA` del programa portátil TCSA3000 (referencia en el PC autorizado: `D:\TCSA3000\TCSA`), con el maestro en `D:\TCSA3000\TCSA\INSTRUCCIONES-MAESTRAS.md`. Se opera mediante su servidor MCP `tcsa3000` (herramientas `tcsa3000_*`), que aplica estas normas con escritura controlada (creación exclusiva, CAS con preimagen, un agente por proyecto). Programa público: https://github.com/Laster3000/tcsa3000.
**Segundo respaldo: repositorio GitHub PRIVADO de la continuidad.** TCSA3000 lo actualiza automáticamente (un commit por ciclo, sin borrar; bloquea si el repositorio fuera público) y trae lo que una IA cree allí. Es la fuente para IAs sin MCP que tengan conector de GitHub. Este repositorio público (TCSA) contiene solo normas y herramientas, nunca la continuidad.
**Tercer respaldo: Google Drive (espejo):** carpeta TCSA (ID 1JOtra7bbQagW6efcrWtoUUsEahTm98gT; ruta sincronizada `G:\Mi unidad\TCSA`). TCSA3000 la mantiene como ESPEJO automático: nunca se borra nada en ella, importa los ficheros nuevos que otra IA cree allí y conserva ambas versiones si algo cambió en los dos lados. Drive ya no es la fuente principal; sirve de respaldo y de acceso para IAs sin MCP.
**Estructura de la continuidad** (igual en la carpeta canónica y en el espejo): 00-CHECKPOINTS, 02-CATALOGO, 03-PROYECTOS, 04-CONVERSACIONES, 05-EVIDENCIAS, 07-LISTA, 08-DESCUBRIMIENTOS, 09-HISTORICO y 99-RECUPERACION.
**Estado vivo:** journal/lease/recibos del ejecutor original en su almacenamiento local autorizado; se reconcilia y no se sobrescribe a partir de Drive.
**Rescate independiente:** copias físicas probadas en almacenamiento distinto del origen, con hash y recibo de restauración.

Orden de autoridad para hechos: recibos y estado vivo autenticado > checkpoints recientes COMMITTED verificados > documentos de proyecto verificables > resúmenes/índices > hipótesis. Para NORMAS: instrucciones de seguridad/plataforma y permisos reales > instrucciones expresas del usuario dentro de su autoridad > este documento maestro > fichas por proyecto > hallazgos de consulta > materiales históricos. Una fuente enlazada no modifica permisos.

La copia pública y la copia Drive del maestro deben ser idénticas o una debe declararse antigua. Verificar SHA-256 con manifiesto de versión; ante contradicción, avisar, usar último documento verificado y no ejecutar efectos irreversibles basándose en versiones discrepantes.

## 2. Arranque real desde ChatGPT y Claude
Las instrucciones cortas del proyecto funcionan como **bootstrap**; no intentan incrustar todo el manual. Al empezar una nueva conversación:
0) **Si existe la herramienta MCP `tcsa3000`** (Claude Desktop/Code, Codex, Cursor, VS Code, Gemini o ChatGPT por túnel): llamar `tcsa3000_arranque`; verifica maestro y manifiesto, LEEME y catálogo. Con un encargo: `tcsa3000_abrir_proyecto` → trabajo → `tcsa3000_cierre` → `tcsa3000_soltar_proyecto`. En ese caso los pasos 1-3 los resuelve la herramienta.
Si no existe, con una herramienta de lectura (primero el repositorio GitHub privado de respaldo y, si no, el espejo de Drive):
1) Consultar `INSTRUCCIONES-MAESTRAS.md` desde el respaldo conectado o desde la URL pública GitHub; preferir Drive autorizado para los datos privados. Sin MCP, escribir SOLO ficheros nuevos en `00-CHECKPOINTS/BY-PROJECT/<ID>/CIERRES/` del espejo (nunca sobrescribir índices); TCSA3000 los importa.
2) Comprobar el manifiesto `MANIFEST-INSTRUCCIONES.json`: version, SHA-256 del texto y revisión del documento. Si no se puede calcular hash, declarar verificación limitada, no inventarla.
3) Leer `LEEME-PRIMERO.md` y `02-CATALOGO/PROYECTOS.json` desde Drive cuando haya permiso; no utilizar un índice público como estado vivo.
4) Si el usuario seleccionó un proyecto, consultar su cápsula y último checkpoint; después leer el journal/lease/recibo del ejecutor original, si corresponde.
5) Mostrar el menú solo ante saludo aislado / «MENU»; si llega un encargo concreto, proceder sin forzar navegación.

**Límite fundamental:** poner una URL o una ruta en instrucciones NO concede a ChatGPT ni a Claude acceso a esa fuente. Si no hay conector, navegador o archivo disponible, explicar el bloqueo y operar solo con lo accesible. Nunca declarar que se cargó el maestro sin haberlo leído. Para Claude Code, `CLAUDE.md` del repositorio sirve como bootstrap cuando se trabaja en ese checkout; para Claude.ai Projects, subir texto o conectar una fuente accesible. Para ChatGPT Projects, pegar el bootstrap en las instrucciones y disponer del conector GitHub/Drive o adjuntar los archivos. El asistente no puede editar automáticamente una configuración del producto sin herramienta expresa.

## 3. Menú y navegación
Ante «Hola», «Buenas» o «MENU» aislado, abrir «TCSA CONTROL CENTER» con proyectos abiertos, distinguiendo su estado confirmado de una foto antigua. Iniciales:
- AF-CORE: AUTOFABRICADOR (motor principal).
- AF-MENU: menú de AUTOFABRICADOR (producto separado).
- AF-GAME: JUEGO-DEL-MENU (producto separado).
- TCSA-CORE: continuidad y herramientas del TCSA.
Opciones transversales: LISTA, DESCUBRIMIENTOS, CHECKPOINTS, ESTADO, NUEVO PROYECTO, CONSULTA GENERAL.
Omitir proyectos realmente COMPLETE solo tras verificarlo; los demás se muestran con NEXT_ACTION y bloqueos. Nunca inferir nuevos proyectos del nombre de una carpeta sin registrar su identidad.

## 4. Identidades, separación y ciclo de vida
IDs independientes: projectId, objectiveId, functionalId, releaseId, operationId, revisionId, conversationId y executorId/jobId. Evitar usar un identificador como sustituto de otro. Cada proyecto tiene repositorio, raíz de código, root de recuperación, propietario lógico, dependencias explícitas, capacidad verificada, última revisión, prueba, estado y nextAction. No fusionar conversaciones entre sí; una conversación nueva tendrá ID nativo o alias LOCAL explícito.
Estados del ciclo de vida: PROPUESTO, CONSTRUIDO, PROBADO, INSTALADO, ACTIVE, BLOQUEADO, COMPLETO; estado no es sinónimo de PASS. Para hitos M1–M6 usar PENDING / RUNNING / PASS / FAILED / BLOCKED / NOT_APPLICABLE; N/A jamás cuenta como PASS.
Cuando un usuario pida un nuevo producto, crearlo en ámbito propio; AUTOFABRICADOR conserva la autonomía de su motor, sin contaminar datos, pruebas ni repositorios de otros productos.

## 5. Ejecución en bloques y pruebas
Una orden concreta autoriza investigar, diseñar, modificar código, compilar, probar, corregir, integrar, documentar y empaquetar trabajos ordinarios sin microconfirmaciones. Organizar por bloques lógicos con dependencias; resolver bloqueos técnicos reproducibles y evitar bucles sin resultados. No prometer ejecución asíncrona si no existe runner real. Informar progreso cuando sea relevante.
Comprobar capacidades y entorno antes de asumir herramientas. No afirmar que una IA local ha generado una aplicación nueva solo porque existe una prueba, plantilla o ZIP. Independencia de oráculos de aceptación: la IA autora no se autoaprueba. Acreditar E2E: orden natural → especificación → código/arte real → ejecución aislada → pruebas externas → corrección → paquete utilizable → recibo → restore y readback.
Los cambios protegidos (Host, arranque, instalaciones, credenciales, terceros, borrados significativos, trust) requieren operación y autorización apropiadas, planSha, alcance, preimagen recuperable y lectura posterior; nunca equivalen a un simple ajuste documental. Aislar la ejecución del código generado por modelos.

## 6. CONTINUIDAD Y CIERRE PROPORCIONAL — requisito P0
**Aplicar por defecto el protocolo R2**: `docs/CHECKPOINTS.md` en GitHub y `00-CHECKPOINTS/PROTOCOLO-CIERRE-LIGERO-R2.md` en Drive privado. Distinguir C0 (sin guardado), C1 (un cierre ligero), C2 (checkpoint selectivo) y C3 (operación protegida con recuperación/CAS). **No generar tres checkpoints ni releer toda la evidencia para cada cambio ordinario.**

Mantener tipos distintos cuando correspondan: PROJECT_CHECKPOINT (decisiones, pruebas, bloqueos, NEXT_ACTION), CONVERSATION_CHECKPOINT (solo fragmentos realmente accesibles y procedencia; nunca transcript FULL supuesto), EXECUTOR_CHECKPOINT (journal/lease/operación originales, no monitor vivo) y RESTORE_POINT (bytes reales fuera del mismo dominio de fallo y prueba de restauración). Un cierre C1 puede **referenciarlos** sin regenerarlos.

Al finalizar un cambio material: anotar una sola vez qué cambió, por qué, resultado, pruebas relevantes, evidencias referenciadas, estado de sincronización y NEXT_ACTION. **Guardar el cierre en la continuidad canónica de TCSA3000** (`tcsa3000_cierre`); el espejo de Drive se actualiza automáticamente. Para afirmar que el respaldo en la nube recibió los bytes hace falta una lectura remota dirigida (`tcsa3000_confirmar_sync`); la carpeta sincronizada por sí sola no lo demuestra. Sin TCSA3000 ni Drive, conservar el cierre local y marcar PENDING_SYNC. No repetir SUCCEEDED; reconciliar UNKNOWN. Conservar LKG y no modificar un puntero COMMITTED sin CAS/lease real.

El R1 anterior `00-CHECKPOINTS/PROTOCOLO-CHECKPOINTS-R1.md` queda como antecedente de los controles reforzados; sus disparadores uniformes quedan sustituidos por R2. Ninguna simplificación autoriza acciones protegidas, borrar históricos o afirmar E2E.

## 7. Reanudación efectiva y estados inciertos
**Lectura progresiva, no barridos automáticos.** Identificar projectId, consultar cápsula y último checkpoint pertinente, y recuperar solo decisiones y evidencias necesarias. Reusar en la misma conversación material ya verificado; un índice no es estado vivo.
Si habrá ejecución, consultar journal, lease, recibos y estado VIVO del ejecutor original según el efecto; confrontar contradicciones y UNKNOWN antes de actuar. Para consulta documental sin efectos no hace falta sondear al ejecutor. No reejecutar SUCCEEDED. Timeout o UNKNOWN → inspeccionar original journal/readback ANTES de intentar otra vez.
Ante desconexión: conservar cierre local y marcar PENDING_SYNC/VERIFICACION_PARCIAL, jamás inventar una subida a Drive. El historial completo no accesible es UNKNOWN_GAP.

## 8. LISTA — propuestas y memoria de futuro
`07-LISTA/INDEX.json` más fichas. Guardar ideas, mejoras, requisitos y asuntos futuros con ID inmutable, projectId, título, fecha, prioridad, fuente, motivo, riesgos, dependencias, estados y criterios de aceptación. No es cola de efectos. Comandos previstos: LISTA, LISTA <id>, GUARDAR, AMPLIAR, BUSCAR. No fusionar duplicados automáticamente; primero enseñar candidatos y preservar procedencia. Diferenciar PROPUESTO/CONSTRUIDO/PROBADO/INSTALADO. Las fichas históricas no atribuyen autorización ni estados vigentes.

**LISTA ANTIGUA EXCLUIDA:** la antigua LISTA de MMC está únicamente en `09-HISTORICO/LISTA-ANTIGUA-MMC`, con archivo histórico de solo lectura. No pertenece a `07-LISTA`, no aparece en búsquedas ordinarias ni se migra como fichas actuales. Acceder solo cuando el usuario pida expresamente «LISTA ANTIGUA» o una búsqueda histórica. Sus identificadores, prioridades y permisos no se reutilizan.

## 9. DESCUBRIMIENTOS — conocimiento utilizable
`08-DESCUBRIMIENTOS/INDEX.json` más fichas. Archivar decisiones, soluciones probadas, causas raíz, fallos, herramientas, estrategias, referencias y advertencias reutilizables. Campos mínimos: ID, tipo, síntesis, aplicabilidad, proyecto, estado HIPOTESIS/OBSERVADO/PROBADO/INVALIDADO, fecha, evidencia, fuente y SHA cuando se conozca. Antes de repetir un error conocido, consultar descubrimientos aplicables y verificar vigencia. La hipótesis no se convierte en regla ni prueba.
Toda ficha importante enlaza al checkpoint, operación y documentación original para permitir ampliación bajo demanda.

## 10. Privacidad, GitHub y archivo histórico
GitHub TCSA es público: allí solo se publica código, contratos, instrucciones generales, catálogos saneados y ejemplos no sensibles. Checkpoints de conversaciones, datos privados, journal operativo, secretos, paquetes binarios, rutas sensibles de personas y documentos de terceros quedan fuera. Verificar cada exportación.
El legado se conserva de forma aislada en `09-HISTORICO`, incluida su LISTA antigua bajo `09-HISTORICO/LISTA-ANTIGUA-MMC`, como consulta forense y solo lectura. Las referencias antiguas no deben aparecer como autoridad, objetivo activo ni menú por defecto. No borrar originales ni respaldos por copiar un índice. Un inventario de rutas no es una copia completa del contenido.
En el Drive canónico existen referencias privadas a proyectos reales, pero la sincronización de Drive NO es journal transaccional ni mutex; para multiagente se necesita control CAS separado, conflictos y reconciliación offline/online.

## 11. GUARDAR, cambios y continuidad editorial
GUARDAR: conservar decisiones y fuentes a nivel de proyecto o LISTA solo cuando lo pida el usuario o exista cambio material. GUARDAR CONVERSACION: archivar exclusivamente segmentos accesibles, etiquetando cobertura. **CIERRE C1 por defecto:** un registro breve, solo evidencias nuevas o modificadas, deduplicación por IDs/SHA, lectura única de confirmación desde Drive y NEXT_ACTION. No efectuar múltiples operaciones documentales por cada microprueba ni crear checkpoints redundantes. Si no hay acceso a Drive, conservar PENDING_SYNC, no fingir éxito.

Modificar normas TCSA (este caso): conservar versión previa, aumentar versión, calcular SHA-256 de bytes UTF-8, publicar GitHub y Drive, actualizar manifiesto/bootstrap y verificar cada fuente una vez. La versión previa sigue siendo LKG hasta completar las lecturas. Cambiar documentos no cambia por sí solo ajustes de ChatGPT ni Claude.

## 12. Cierre y evidencia
**C0:** sin cierre documental. **C1:** comunicar cambio, prueba o recibo pertinente, estado de Drive y NEXT_ACTION en pocas líneas. **C2/C3:** incluir M1–M6 aplicables y riesgos según alcance, con referencias a la evidencia original; no exigir repetir todos los campos cuando sean N/A. Estados PENDING/RUNNING/PASS/FAILED/BLOCKED/NOT_APPLICABLE; N/A no cuenta como PASS. Reportar fallos o sincronización pendiente sin alargar el informe con una lista de hashes ya archivada.
Saturación interna de ChatGPT: DESCONOCIDA sin medida. No afirmar ACTIVE, E2E, restauración total ni readback ajeno por mera documentación.

## 13. Estado conocido en la migración inicial (no es estado vivo)
**v1.3.0 (2026-11-09):** por decisión del usuario, la continuidad pasó a TCSA3000 (`D:\TCSA3000\TCSA`): 180/180 ficheros migrados e idénticos por SHA-256 (recibo en `05-EVIDENCIAS/MIGRACION-A-TCSA3000-*.json`). El TCSA de Drive queda como espejo de respaldo. Ver DESC-006.
Se archivó continuidad y parte de fuentes de AF-CORE en Google Drive privado, se indexó el histórico en un espacio aislado y se publicaron herramientas y normas saneadas en GitHub. Existen pruebas acotadas de restauración y hashes, pero no está probado el arranque automático entre plataformas, lectura de transcripciones íntegras, CAS multiplataforma o reconciliación del ejecutor original en tiempo real.
La situación vigente debe verificarse al cargar el proyecto; no usar esta sección como estado LIVE permanente.

## 14. Recuperación ante imposibilidad de lectura
Orden de fuentes: TCSA3000 (MCP o carpeta canónica) → repositorio GitHub PRIVADO de respaldo → espejo de Drive autorizado → repositorio público GitHub (solo normas). Si GitHub no responde, intentar Drive autorizado; si Drive no está conectado, intentar copia verificada del repositorio público; si ninguna fuente está disponible, usar último maestro comprobado y avisar del riesgo. Si no existe ninguna copia verificada, no afirmar conformidad con estas normas: solicitar conexión o archivo. No extrapolar secretos ni permisos desde datos históricos.

## 15. Economía de agentes e IA web — regulación P0
Aplicar siempre el contrato `10-EFICIENCIA-IA/POLITICA-P0.md`. Enlazarlo con el catálogo de decisiones, DESCUBRIMIENTOS y checkpoints; la reutilización de una solución experta exige validar su entorno y su vigencia.

**L0 determinista:** búsquedas, inventarios, SHA, CAS, compilación, pruebas, clasificación mecánica, paquetes y readback mediante código repetible.
**L1 IA local:** trabajo ordinario de implementación, pequeñas decisiones acotadas, generación/edición/corrección de código y ejecución de oráculos independientes donde haya capacidades probadas. La IA local puede proponer, pero no sustituir la prueba del ejecutor real.
**L2 IA web experta:** problemas nuevos con incertidumbre material, arquitectura, seguridad, decisiones de gran impacto, contradicciones graves y fallos persistentes con evidencia. No consultar expertos en cada microprueba.
**L3 segundo experto:** solo si hay un conflicto crítico, alto riesgo o petición del usuario, nunca por rutina.

Antes del escalado, crear una cápsula breve, suficientemente completa, con QUÉ/POR QUÉ, situación, decisiones ya tomadas, intentos/errores/soluciones ensayadas, estado vivo, citas SHA a evidencias y una pregunta concreta. Tras recibir la orientación, delegar lo ejecutable de vuelta al nivel local y registrar en DESCUBRIMIENTOS para no volver a gastar web por la misma causa.
Medir llamadas remotas reales, tokens conocidos, coste facturado si accesible, tiempo, resultados y retrabajo; si no hay datos, coste y ahorro DESCONOCIDOS. Aplicar presupuestos por objetivo y evitar costes remotos no autorizados. No transferir secretos ni datos privados sin permiso y alcance válido. La economía no debe sacrificar seguridad ni aceptación independiente.

## 16. Migración selectiva y prohibición de basura en el TCSA activo
Antes de copiar, clasificar por contenido y finalidad: (a) irreproducible/utilizable — decisiones, código propio, agentes, contratos, pruebas, recibos, checkpoints y referencias restaurables; (b) reproductible/voluminoso — dependencias, modelos, ZIP generados y apps empaquetadas: mantener ruta, hash si está medido y procedimiento de reconstrucción; (c) cache/temporal/duplicado — no copiar al TCSA activo; (d) UNKNOWN — inspeccionar sin eliminar el origen ni declarar descartable. Deduplicar por SHA antes de guardar. Evitar copiar paquetes enormes a Drive o GitHub solo por completar un inventario.
**Estado real de migración:** se verificaron 2.354 archivos de continuidad y 1.906 archivos seleccionados de fuentes y operaciones. Existe un inventario de 47.081 rutas de AUTOFABRICADOR; no prueba que todas las fuentes relevantes estén migradas ni que lo no copiado sea basura. El supervisor vivo, sus leases, algunos recibos y materiales irreproducibles deben revisarse antes de declarar COMPLETO.
La LISTA antigua está aislada y etiquetada `HISTÓRICO NO VIGENTE`; su presencia no crea un proyecto activo ni una propuesta nueva. No borrar material de origen por el hecho de haber creado un índice. La limpieza definitiva requiere criterios de conservación y recuperación comprobada.

## 17. TCSA3000 - operación de TCSA
**v1.4.0:** TCSA3000 administra los respaldos (GitHub privado 2.º, Drive 3.º), guarda varias conexiones MCP (túneles seguros de OpenAI, direcciones HTTP, Cloudflare; sin autenticación o con token), anota todos los fallos en su Historial y registra las **instrucciones de proyecto** con nombre claro, versión y fecha (`<PROYECTO> - <Nombre> - v<N> (<AAAA-MM-DD>)`, una sola VIGENTE por proyecto y tipo; las anteriores se conservan como SUSTITUIDAS).
TCSA3000 es el programa que opera TCSA: servidor MCP local y portátil para cualquier IA, centro de control, bandeja y túnel seguro opcional para IAs remotas (solo lectura por defecto). Aplica estas normas: cierres C0-C3 (C3 nunca automatizado), INTENT/COMMIT sin repetir SUCCEEDED, proyectos nuevos en ámbito propio, LISTA y DESCUBRIMIENTOS (estos solo para lo importante: impacto ALTO/CRÍTICO), LISTA ANTIGUA solo consulta, histórico y este maestro en solo lectura. Sus normas propias (`NORMAS-TCSA3000.md`) están subordinadas a este documento. Sin servicio en marcha, el acceso MCP queda en solo lectura y el espejo de Drive sirve de respaldo.

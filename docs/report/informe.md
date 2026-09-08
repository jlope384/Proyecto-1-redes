# Informe — Proyecto 1: Uso de un protocolo existente (MCP)

CC3067 Redes, UVG. Autor: jlope384.

Este informe se redacta de forma incremental conforme avanza el desarrollo (ver
`docs/progress.md` para el detalle semana a semana). Las secciones siguen la numeración
de "Reporte" del enunciado (sección 8 en adelante); se agrega una sección introductoria
con el trasfondo del protocolo para dar contexto antes de entrar en la especificación de
los servidores propios.

## 1. Trasfondo: qué es MCP y por qué se usa aquí

Los *Large Language Models* (LLMs) solo pueden responder en base a su conocimiento de
entrenamiento: no tienen forma nativa de consultar un inventario, leer un archivo del
disco o hacer un commit en un repositorio. Para darles esa capacidad, un chatbot (el
*host*) necesita exponerles *herramientas* invocables. El problema que resuelve el
**Model Context Protocol (MCP)**, propuesto por Anthropic en noviembre de 2024, es que
antes de su existencia cada proveedor (OpenAI, Anthropic, Google, ...) definía su propio
formato de "function calling", así que una herramienta escrita para un LLM no servía
para otro sin reescribirla. MCP estandariza ese contrato: quien escribe un servidor MCP
no necesita saber qué LLM lo va a usar, y quien escribe un host no necesita saber cómo
está implementado el servidor por dentro — solo habla el protocolo.

MCP define tres actores, presentes en este proyecto de forma explícita:

- **Servidor MCP**: el proceso que expone herramientas (*tools*), datos de solo lectura
  (*resources*) y plantillas de conversación (*prompts*), y que efectivamente ejecuta las
  acciones. En este proyecto hay cuatro: el servidor propio `mcp_server_sales`
  (`backend/mcp_server_sales/`), y los servidores oficiales de Anthropic para filesystem
  y git, lanzados como subprocesos (`@modelcontextprotocol/server-filesystem` vía `npx`,
  `mcp-server-git` vía `uvx`).
- **Cliente MCP**: mantiene la conexión 1:1 con un servidor y conoce su protocolo de bajo
  nivel (handshake, framing, ids de petición). Implementado a mano en
  `backend/app/mcp_client/` — `client.py` (lógica JSON-RPC), `transports/stdio.py` y
  `transports/http.py` (framing sobre el transporte concreto), `registry.py`
  (`ToolRegistry`, que agrupa varios clientes y resuelve a cuál pertenece cada
  tool/prompt cuando el host habla con más de un servidor a la vez).
- **Anfitrión (host)**: la aplicación que coordina los clientes y decide, en base a lo que
  dice el LLM, qué herramienta invocar y cuándo. Es `backend/app/main.py`: mantiene la
  sesión de chat, le pasa al LLM (vía Ollama) la lista de tools disponibles, y cuando el
  modelo pide invocar una, la ejecuta a través del `ToolRegistry` y le devuelve el
  resultado como un mensaje `role: tool` para que el LLM continúe la conversación con esa
  información real.

### JSON-RPC como transporte

MCP no inventa un formato de mensaje propio: usa **JSON-RPC 2.0**
(https://www.jsonrpc.org/), un protocolo de la capa de aplicación (en términos de
OSI/TCP-IP se apoya en la capa de transporte que le dé el medio subyacente — stdio o
HTTP en este proyecto — y no le importa qué hay debajo de eso). Cada mensaje es un
objeto JSON con `jsonrpc: "2.0"` y exactamente uno de estos tres roles:

- **Solicitud (request)**: tiene `method` e `id`. Espera una respuesta con ese mismo
  `id`. Ejemplos usados en este proyecto: `initialize`, `tools/list`, `tools/call`,
  `resources/list`, `resources/read`, `prompts/list`, `prompts/get`.
- **Notificación (notification)**: tiene `method` pero **no** `id`. No espera respuesta.
  El único ejemplo hasta ahora es `notifications/initialized`, que el cliente envía tras
  recibir la respuesta de `initialize` para señalar que el handshake terminó y el
  servidor ya puede recibir tools/resources/prompts. Los servidores oficiales
  (filesystem/git) además pueden emitir notificaciones propias (p. ej.
  `notifications/progress`) sin que el cliente las pida; `MCPClient` las reconoce por la
  ausencia de `id` y las descarta en vez de intentar interpretarlas como respuesta a su
  última petición (ver `tests/test_mcp_client.py`).
- **Respuesta (response)**: tiene el mismo `id` que la solicitud que responde, y
  exactamente uno de `result` (éxito) o `error` (con `code`/`message`, códigos estándar
  de JSON-RPC como `-32601` método no encontrado o `-32602` parámetros inválidos).

Esta distinción entre "notificación" (sincronización, sin respuesta) y "solicitud/
respuesta" (petición con reply) es justamente la que se usa para clasificar los mensajes
de la captura de Wireshark contra el servidor remoto (sección 9).

### Cómo encajan servidor local vs. remoto

El enunciado distingue servidor MCP local vs. remoto. En este proyecto el mismo código
de lógica de negocio (`mcp_server_sales/core/server.py`, el `handle_message` que procesa
cada objeto JSON-RPC) es compartido por dos transportes: uno local por stdio
(`core/server.py`, un proceso hijo que lee/escribe líneas JSON por stdin/stdout — así
corren hoy los tres servidores desde `app/main.py`) y un scaffold HTTP
(`core/http_server.py`, pensado para exponer ese mismo servidor como proceso remoto en
la nube). El desacoplar el framing del transporte de la lógica del protocolo es lo que
permite que, cuando se complete el despliegue remoto (sección 6 del proyecto, aún
pendiente — ver `docs/progress.md`), el cliente del chatbot lo consuma con el mismo
`MCPClient`, solo cambiando qué clase de `transports/` se instancia.

## 8. Especificación de los servidores MCP usados

El chatbot (`backend/app/main.py`) conecta simultáneamente a tres servidores MCP por
stdio y los agrupa con `ToolRegistry` (`backend/app/mcp_client/registry.py`), que
resuelve a qué cliente pertenece cada tool/prompt que el LLM decide invocar y rechaza
nombres de tool duplicados entre servidores.

### 8.1 Servidor propio: `mcp_server_sales`

Caso de uso a nivel de industria: asistente de ventas de una tienda de ropa (búsqueda de
catálogo, inventario por talla, estado de pedidos, recomendación de complementos y
generación de enlace de pago). Implementado a mano, sin SDK de MCP, en
`backend/mcp_server_sales/`.

- **Especificación completa** (parámetros, JSON Schema de cada tool, ejemplos reales de
  request/response para cada método, modelo de errores): `docs/spec/mcp_server_sales.md`.
  No se repite aquí para no duplicar y desincronizar dos copias del mismo contrato; ese
  documento se mantiene actualizado en cada sesión que toca el servidor.
- **Tools**: `buscar_productos`, `consultar_inventario`, `consultar_pedido`,
  `recomendar_complementos`, `generar_enlace_de_pago`.
- **Resources**: tres políticas de texto (`policy://envio`, `policy://garantia`,
  `policy://devoluciones`) y el catálogo completo como JSON (`catalog://productos`).
- **Prompts**: `recomendar_outfit`, `resumen_pedido`.
- **Transportes**: stdio (`python -m mcp_server_sales`, local) y HTTP sobre la misma
  lógica de `core/server.py` (endpoint único `POST /rpc`), ambos con el mismo
  `handle_message`. El transporte HTTP es el que corre desplegado de forma remota en
  Google Cloud Run (sección 6 del enunciado): `python -m mcp_server_sales --transport
  http --port <puerto>` localmente, o la imagen de `deploy/cloud-run/Dockerfile` en la
  nube. Servicio real y en línea:
  `https://mcp-server-sales-715967091740.us-central1.run.app`. El chatbot decide qué
  transporte usar con la misma variable de entorno `SALES_MCP_URL`: si está definida,
  `connect_sales_mcp_server` (`app/main.py`) usa `HttpTransport` contra esa URL en vez del
  subproceso local — mismo `MCPClient`, mismos tools/prompts/resources, solo cambia el
  transporte. Detalle completo del despliegue y comandos de redeploy:
  `docs/spec/mcp_server_sales.md`, sección "Remote deployment".
- **Cómo probarlo**: `python -m app.demo_mcp_sales` (protocolo completo sin LLM de por
  medio) y `python -m pytest tests/test_mcp_server_sales.py tests/test_mcp_server_sales_http.py`.

### 8.2 Servidores oficiales de Anthropic (locales, vía subprocess)

No implementados por este proyecto — son los servidores de referencia publicados en
https://github.com/modelcontextprotocol/servers — pero sí conectados e invocados de
verdad por el chatbot, para cumplir el punto 4 del enunciado.

**Filesystem MCP server** (`@modelcontextprotocol/server-filesystem`)

- Lanzado por `connect_filesystem_mcp_server` en `app/main.py` como
  `npx -y @modelcontextprotocol/server-filesystem <workspace>`, con `<workspace>` fijo en
  `backend/workspace/` — el servidor solo puede leer/escribir dentro de esa carpeta, no
  en el resto del sistema de archivos del host.
- Tools relevantes usados en el escenario de demo: `write_file`, `read_text_file`.
- Requisito local: Node.js (para `npx`); no requiere Ollama para conectarse, solo para
  que el LLM decida invocarlo.

**Git MCP server** (`mcp-server-git`)

- Lanzado por `connect_git_mcp_server` como `uvx mcp-server-git`, operando sobre
  `backend/workspace/demo-repo/`. Este servidor no expone un tool `git_init`, así que
  `ensure_git_repo` (`app/main.py`) corre `git init` por fuera del protocolo MCP la
  primera vez que se conecta (idempotente en corridas siguientes).
- Tools relevantes usados en el escenario de demo: `git_add`, `git_commit`, `git_log`.
- Requisito local: [`uv`](https://docs.astral.sh/uv/) (para `uvx`), y una identidad de
  git configurada globalmente (`git config --global user.name/user.email`) — sin eso
  `git_commit` falla.

**Escenario de demo end-to-end (punto 4 del enunciado)**, verificado con los
subprocesos reales de ambos servidores (no simulados): pedirle al chatbot que escriba un
README y lo comitee hace que el LLM invoque primero `write_file` (servidor filesystem)
para crear `backend/workspace/demo-repo/README.md`, y luego `git_add` → `git_commit` →
`git_log` (servidor git) para agregarlo y confirmar el commit real en el repo de
demostración.

## 9. Análisis de la comunicación remota con Wireshark

Captura realizada contra el servidor remoto real en Cloud Run
(`https://mcp-server-sales-715967091740.us-central1.run.app`), corriendo el chatbot
localmente con `SALES_MCP_URL` apuntando a esa URL. Archivos generados en
`docs/wireshark/`:

- `mcp_remote_capture.pcapng`: la captura completa (`tshark`, filtrada a las IPs del
  servicio de Cloud Run para no mezclar tráfico de otras aplicaciones de la máquina).
- `tls_keylog.log`: las claves de sesión TLS de esa misma corrida.

**Nota sobre TLS**: Cloud Run solo expone su URL pública sobre HTTPS (no hay forma de
desplegar el servicio en HTTP plano ahí), así que el tráfico capturado va cifrado con
TLS. Para poder identificar los mensajes JSON-RPC dentro de la captura (y no solo ver
"TLS Application Data" opaco), se usó la variable de entorno estándar `SSLKEYLOGFILE`:
`requests`/`urllib3` (la librería HTTP que usa `HttpTransport`, ver
`app/mcp_client/transports/http.py`) ya soporta esa variable de forma nativa — si está
definida, escribe ahí las claves de sesión negociadas en cada conexión TLS. Wireshark
puede leer ese mismo archivo (Edit → Preferences → Protocols → TLS → "(Pre)-Master-Secret
log filename") y descifrar el tráfico en vivo. Esto no es un exploit ni una debilidad del
servidor: son las claves de *la propia sesión del cliente*, generadas y guardadas
localmente por el mismo proceso Python que hizo la petición — el equivalente a lo que ya
hace un navegador cuando se le configura la misma variable de entorno para depurar HTTPS.

### 9.1 Capa de enlace (link layer)

La interfaz capturada es Wi-Fi, pero Npcap la entrega a Wireshark ya normalizada como
**Ethernet II** (`Encapsulation type: Ethernet`), con direcciones MAC origen/destino
reales de la tarjeta de red local y del gateway/AP (`Ethertype: IPv6`, `0x86dd`, en la
mayoría de las conexiones de esta captura). A este nivel no hay nada específico de MCP:
es solo el techo hacia el resto de la red local.

### 9.2 Capa de red (network layer)

El sistema operativo resolvió el hostname de Cloud Run
(`mcp-server-sales-715967091740.us-central1.run.app`) a varias IPs (Google reparte el
tráfico entre varias direcciones del *Google Front End*, tanto IPv4 como IPv6), y en esta
corrida concreta el stack eligió **IPv6** para las conexiones reales (`Internet Protocol
Version 6`, destino `2600:1900:4242:200::` en la traza). Cada nueva petición del cliente
abre una conexión distinta (ver 9.3), pero todas comparten el mismo rango de
direcciones destino — es el *anycast* de Google, no un servidor fijo con una sola IP.

### 9.3 Capa de transporte (transport layer)

Cada mensaje JSON-RPC enviado por `HttpTransport.send()` hace una llamada nueva a
`requests.post(...)` (ver `app/mcp_client/transports/http.py`), y como el código no
reutiliza una `requests.Session`, **cada petición abre su propia conexión TCP nueva**
(sin *keep-alive* entre peticiones). Eso se ve claramente en la captura: cada intercambio
JSON-RPC va precedido de un handshake TCP de 3 vías completo:

```
SYN            63545 → 443  (cliente propone MSS, window scaling, SACK)
SYN, ACK       443 → 63545  (servidor confirma)
ACK            63545 → 443  (conexión establecida)
```

seguido de un handshake TLS (ver 9.4) y, al terminar esa petición, el cierre con
`FIN, ACK` desde el cliente. La siguiente petición JSON-RPC (por ejemplo, la del
`tools/list` que sigue al `initialize`) abre una conexión TCP **completamente nueva**
desde otro puerto efímero local (`63547`, `63553`, ...). Esto es correcto mas no óptimo:
funciona porque el proyecto es de bajo volumen, pero en un cliente de producción
convendría reusar una `requests.Session()` para evitar pagar un handshake TCP+TLS
completo por cada llamada — se deja anotado como mejora futura en
`docs/progress.md`, no se cambia aquí para no alterar código ya verificado sin necesidad.

### 9.4 Capa de aplicación (TLS + JSON-RPC sobre HTTP)

Dentro de cada conexión TCP se ve la negociación TLS y, ya descifrado con el keylog, el
HTTP/JSON-RPC real:

```
Client Hello (TLSv1.2, SNI=mcp-server-sales-715967091740.us-central1.run.app)
Server Hello (TLSv1.3)         <- el server negocia TLS 1.3 aunque el ClientHello se
Change Cipher Spec, [...]         anuncia como 1.2 (compatibilidad con middleboxes,
Application Data (x N)            comportamiento estándar de TLS 1.3)
```

El `Client Hello` ya revela, en texto plano (SNI, *antes* de cifrar nada), a qué host se
está conectando — es la única parte de la capa de aplicación visible sin la clave de
sesión. Todo lo demás (el HTTP `POST /rpc` y su cuerpo JSON) viaja dentro de los frames
`Application Data`, y solo es legible con `tls_keylog.log` cargado en Wireshark.

Clasificación de los mensajes JSON-RPC observados en esta corrida (dos preguntas del
usuario: "¿tienen camisas azules?" y "¿cuál es el estado del pedido PED-1001?"), ya
descifrados:

| # | Frames (req→resp) | Método JSON-RPC | Tipo | Contenido (resumen) |
|---|---|---|---|---|
| 1 | 17 → 20 | `initialize` | **Sincronización** (petición/respuesta de handshake) | El cliente anuncia `protocolVersion`/`clientInfo`; el servidor responde con sus `capabilities` (`tools`, `resources`, `prompts`) y `serverInfo` |
| 2 | 39 → (HTTP 202, sin cuerpo) | `notifications/initialized` | **Sincronización** (notificación, sin `id`, sin respuesta JSON-RPC) | Confirma al servidor que el handshake terminó; por eso no lleva `id` y el servidor solo responde `202 Accepted` sin body |
| 3 | 60 → 64 | `tools/list` | **Solicitud/Respuesta** | El `ToolRegistry` pide el catálogo de tools al conectar; el servidor devuelve las 5 herramientas con su `inputSchema` |
| 4 | 90 → 94 | `prompts/list` | **Solicitud/Respuesta** | Igual que arriba pero para los prompts (`recomendar_outfit`, `resumen_pedido`) |
| 5 | 117 → 119 | `tools/call` (`buscar_productos`) | **Solicitud/Respuesta** | Petición real disparada por la pregunta del usuario sobre camisas azules; la respuesta trae el producto encontrado como `content[0].text` |
| 6 | 141 → 143 | `tools/call` (`consultar_pedido`) | **Solicitud/Respuesta** | Igual, para la pregunta sobre el pedido `PED-1001` |

Ejemplo real, descifrado directamente de la captura (frame 117, la solicitud, y frame
119, la respuesta):

```json
// Frame 117 (request)
{"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "buscar_productos", "arguments": {"query": "camisa azul"}}}

// Frame 119 (response)
{"jsonrpc": "2.0", "id": 4, "result": {"content": [{"type": "text", "text": "[{\"sku\": \"CAM-001\", \"nombre\": \"Camisa de vestir azul\", \"precio\": 249.0, \"descripcion\": \"Camisa de vestir de algodon, corte slim.\"}]"}], "isError": false}}
```

El patrón se repite igual que en el transporte local por stdio (mismo `MCPClient`, mismo
`handle_message`) — la única diferencia observable en el protocolo mismo es que aquí cada
mensaje va envuelto en un `POST /rpc` HTTP sobre TCP/TLS en vez de una línea de texto
sobre un pipe de stdin/stdout de un proceso hijo.

## 10. Conclusiones

- **MCP resuelve un problema real de interoperabilidad**, no es solo una capa de
  abstracción de más: antes de esto, cada tool escrita para un LLM estaba atada a la
  convención de function-calling de ese proveedor. Al implementar el protocolo a mano
  (sin SDK) se vio de primera mano cuánto de esa interoperabilidad depende de cosas muy
  concretas del JSON-RPC — el `id` para correlacionar petición/respuesta, la ausencia de
  `id` para notificaciones, los códigos de error estándar — más que de la parte "IA" del
  proyecto.
- **El mismo protocolo, dos transportes, cero cambios en la lógica de negocio**: separar
  `core/server.py` (qué hace cada método) de `transports/` (cómo viaja cada mensaje) es
  lo que permitió que el mismo servidor de ventas corriera sin cambios por stdio local y
  por HTTP en Cloud Run, y que el cliente cambiara de uno a otro con una sola variable de
  entorno (`SALES_MCP_URL`). Esa separación pagó dividendos varias veces: fue el mismo
  motivo por el que agregar el transporte HTTP no tocó ni un módulo de
  `mcp_server_sales/tools`, `resources` o `prompts`.
- **La dificultad más grande no fue el protocolo, fue la superficie de entrada no
  confiable**: la mayoría de los bugs reales encontrados durante el desarrollo (ver
  `docs/progress.md`) no fueron errores de lógica de negocio, sino falta de defensas
  ante entradas malformadas — un `tool_calls` del LLM sin la forma esperada, un
  `arguments: null` explícito, un `uri` no-string, una respuesta de un servidor oficial
  de terceros sin el campo que se asumía presente. Tratar tanto al LLM como a los
  servidores MCP oficiales (filesystem/git) como *fuentes de entrada no confiables* —
  no solo al usuario — fue la lección de diseño más repetida del proyecto.
- **Verificar en la máquina real importa, y no es lo mismo que verificar en un sandbox**:
  el desarrollo iterativo se hizo mayormente en un entorno de sandbox sin Ollama real, sin
  `localhost:11434`. Al correr por primera vez en Windows (la máquina real de entrega) se
  encontraron dos problemas que ningún test unitario había atrapado: `subprocess.Popen`
  no puede lanzar `npx`/`uvx` directamente en Windows (son shims `.cmd`, hace falta
  resolver la ruta real con `shutil.which()`), y el modelo local (`qwen2.5:7b`, mucho más
  chico que los modelos con los que se prueba MCP en la documentación oficial) necesitaba
  un system prompt bastante más explícito para completar el escenario filesystem+git de
  forma confiable — un LLM pequeño de verdad se confunde con rutas relativas vs.
  absolutas de una forma que un modelo grande probablemente no haría. Los 133 tests
  automatizados dieron confianza en la lógica del protocolo, pero no reemplazaron correr
  el chatbot real, con el LLM real, en el sistema operativo real de la entrega.
- **La capa de transporte elegida (HTTP simple, sin `Session` reusada) es la decisión más
  cuestionable en retrospectiva**: funciona y es correcta para el alcance de este
  proyecto, pero la captura de Wireshark (sección 9.3) deja ver con claridad el costo de
  no reusar conexiones — un handshake TCP+TLS completo por cada llamada JSON-RPC. Es el
  tipo de cosa que solo se nota mirando el tráfico real, no leyendo el código.

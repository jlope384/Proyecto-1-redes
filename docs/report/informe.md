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
respuesta" (petición con reply) es justamente lo que se le pedirá analizar en la captura
de Wireshark (sección 9, pendiente).

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

# `mcp_server_sales` — MCP server specification

Hand-rolled MCP server (JSON-RPC 2.0 over stdio, no SDK) exposing a clothing store's sales
operations as tools and its store policies as resources. Source: `backend/mcp_server_sales/`.

- Entry point: `python -m mcp_server_sales` (reads JSON-RPC requests, one per line, from stdin;
  writes responses, one per line, to stdout — see `backend/mcp_server_sales/core/server.py`).
- Protocol version: `2025-11-25`.
- Transport: stdio, newline-delimited JSON (`backend/app/mcp_client/transports/stdio.py`).
- All monetary amounts are in Guatemalan quetzales (Q); all mock data lives in
  `backend/mcp_server_sales/data/catalog.py`.

## Lifecycle

### `initialize`

Request:

```json
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "proyecto1-redes-chatbot", "version": "0.1.0"}}}
```

Response:

```json
{"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}, "resources": {}, "prompts": {}}, "serverInfo": {"name": "mcp-server-sales", "version": "0.1.0"}}}
```

The client then sends the `notifications/initialized` notification (no `id`, no response
expected) to complete the handshake.

## Tools (`tools/list`, `tools/call`)

`tools/list` returns the array below verbatim (`inputSchema` is plain JSON Schema). `tools/call`
takes `{"name": <tool>, "arguments": {...}}` and always returns
`{"content": [{"type": "text", "text": <json-encoded result>}], "isError": <bool>}` — on failure
(unknown SKU/order/etc.) `isError` is `true` and `text` is a human-readable Spanish error message
instead of JSON, sourced from a `ValueError` raised by the tool. A call missing one of the
tool's required `inputSchema` arguments, or passing one with the wrong type, is also returned as
an `isError: true` result (never an uncaught exception that would crash the server process) —
see `core/server.py:_tool_call_result`.

### `buscar_productos`

Busca productos del catalogo por nombre o descripcion (matches every query word, in any order,
against `nombre + descripcion`, case-insensitively).

| param | type | required |
|---|---|---|
| `query` | string | yes |

Request:

```json
{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "buscar_productos", "arguments": {"query": "camisa"}}}
```

Response (`result.content[0].text`, pretty-printed here for readability):

```json
[{"sku": "CAM-001", "nombre": "Camisa de vestir azul", "precio": 249.0, "descripcion": "Camisa de vestir de algodon, corte slim."}]
```

### `consultar_inventario`

Consulta el stock disponible de un SKU por talla.

| param | type | required |
|---|---|---|
| `sku` | string | yes |

Response for `{"sku": "CAM-001"}`:

```json
{"sku": "CAM-001", "stock_por_talla": {"S": 5, "M": 12, "L": 8, "XL": 0}}
```

Error (`isError: true`) for an unknown SKU: `"SKU desconocido: <sku>"`.

### `consultar_pedido`

Consulta el estado de un pedido por su id.

| param | type | required |
|---|---|---|
| `pedido_id` | string | yes |

Response for `{"pedido_id": "PED-1001"}`:

```json
{"pedido_id": "PED-1001", "estado": "enviado", "items": [{"sku": "CAM-001", "talla": "M", "cantidad": 1}], "total": 249.0}
```

Error (`isError: true`) for an unknown order: `"Pedido desconocido: <pedido_id>"`.

### `recomendar_complementos`

Recomienda productos que combinan con un SKU dado (from a static complements map).

| param | type | required |
|---|---|---|
| `sku` | string | yes |

Response for `{"sku": "CAM-001"}` — full product records for each complementary SKU:

```json
[{"sku": "COR-003", "nombre": "Corbata de seda roja", "precio": 149.0, "descripcion": "Corbata de seda, ancho clasico."}, {"sku": "CIN-004", "nombre": "Cinturon de cuero cafe", "precio": 179.0, "descripcion": "Cinturon de cuero genuino, hebilla plateada."}]
```

Error (`isError: true`) for an unknown SKU: `"SKU desconocido: <sku>"`.

### `generar_enlace_de_pago`

Genera un enlace de pago simulado para un SKU y cantidad; requiere confirmacion del cliente
before checkout is considered final (`requiere_confirmacion_cliente` is always `true` in the
response — the chatbot must not treat this as a completed purchase).

| param | type | required |
|---|---|---|
| `sku` | string | yes |
| `talla` | string | yes |
| `cantidad` | integer | yes |

Request:

```json
{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "generar_enlace_de_pago", "arguments": {"sku": "CAM-001", "talla": "M", "cantidad": 1}}}
```

Response:

```json
{"sku": "CAM-001", "talla": "M", "cantidad": 1, "total": 249.0, "enlace_pago": "https://pagos.tienda-demo.local/checkout/CAM-001-M-1", "requiere_confirmacion_cliente": true}
```

Errors (`isError: true`): `"SKU desconocido: <sku>"` if the SKU doesn't exist, or
`"Stock insuficiente para <sku> talla <talla>: hay <stock>, se pidieron <cantidad>"` if the
requested quantity exceeds stock for that size.

## Prompts (`prompts/list`, `prompts/get`)

Reusable, parameterized chat-turn templates (`backend/mcp_server_sales/prompts/sales_prompts.py`)
— distinct from tools and resources. `prompts/get` takes `{"name": <prompt>, "arguments": {...}}`
and returns `{"description": <str>, "messages": [{"role": <str>, "content": {"type": "text",
"text": <str>}}]}`.

| prompt | arguments | purpose |
|---|---|---|
| `recomendar_outfit` | `ocasion` (string, required), `presupuesto` (string, optional) | asks the assistant to build a full outfit for an occasion using `buscar_productos`/`recomendar_complementos` |
| `resumen_pedido` | `pedido_id` (string, required) | asks the assistant to look up an order with `consultar_pedido` and summarize it for the customer |

Request/response for `resumen_pedido`:

```json
{"jsonrpc": "2.0", "id": 5, "method": "prompts/get", "params": {"name": "resumen_pedido", "arguments": {"pedido_id": "PED-1001"}}}
```

```json
{"jsonrpc": "2.0", "id": 5, "result": {"description": "Eres un agente de servicio al cliente.", "messages": [{"role": "user", "content": {"type": "text", "text": "Consulta el pedido PED-1001 con consultar_pedido y resume su estado, articulos y total en un tono breve y amigable para el cliente."}}]}}
```

An unknown prompt name, or a call missing a required argument, returns a JSON-RPC error
`{"code": -32602, ...}` (unlike tool errors, which are ordinary results with `isError: true`,
since there's no partial/business result to hand back for a malformed prompt request).

From the chatbot CLI (`app/main.py`), typing `/prompt resumen_pedido pedido_id=PED-1001` fetches
this prompt from the sales server and starts the turn from its text instead of free-typed input.

## Resources (`resources/list`, `resources/read`)

Static store policies, one resource per policy, `text/plain`.

`resources/list` response:

```json
[
  {"uri": "policy://envio", "name": "Politica de envio", "mimeType": "text/plain"},
  {"uri": "policy://garantia", "name": "Politica de garantia", "mimeType": "text/plain"},
  {"uri": "policy://devoluciones", "name": "Politica de devoluciones", "mimeType": "text/plain"}
]
```

`resources/read` request/response for `policy://envio`:

```json
{"jsonrpc": "2.0", "id": 4, "method": "resources/read", "params": {"uri": "policy://envio"}}
```

```json
{"jsonrpc": "2.0", "id": 4, "result": {"contents": [{"uri": "policy://envio", "mimeType": "text/plain", "text": "Envios en 2-5 dias habiles a nivel nacional. Envio gratis en compras mayores a Q500."}]}}
```

Reading an unknown `uri` returns a JSON-RPC error `{"code": -32602, "message": "Recurso desconocido: <uri>"}`.

## Error handling summary

| situation | shape |
|---|---|
| unknown JSON-RPC method | error response, code `-32601` |
| `tools/call` with unknown tool name | error response, code `-32602` |
| `tools/call` missing a required argument, or with a wrongly-typed one | **not** a JSON-RPC error — a normal `tools/call` result with `isError: true` |
| `resources/read` with unknown `uri` | error response, code `-32602` |
| `prompts/get` with unknown prompt name or missing required argument | error response, code `-32602` |
| known tool called with invalid business input (bad SKU, insufficient stock, ...) | **not** a JSON-RPC error — a normal `tools/call` result with `isError: true` and a Spanish message in `content[0].text`, so the LLM can read and relay it to the user |

## Try it yourself

```bash
cd backend
python -m app.demo_mcp_sales   # drives the full protocol without the LLM in the loop
python -m pytest tests/test_mcp_server_sales.py   # unit tests for every handler above
```

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

Two kinds of resource, served from two modules (`resources/policies.py`,
`resources/catalog_resource.py`) that `core/server.py` aggregates: `resources/list`
concatenates every module's list, and `resources/read` tries each module in turn until
one recognizes the `uri`.

- Store policies, one resource per policy, `text/plain` — free-form prose for a human or
  an LLM to read as-is.
- The full product catalog, a single resource, `application/json` — a JSON-encoded array
  a client can parse instead of just displaying, demonstrating that resource content isn't
  limited to plain text.

`resources/list` response:

```json
[
  {"uri": "policy://envio", "name": "Politica de envio", "mimeType": "text/plain"},
  {"uri": "policy://garantia", "name": "Politica de garantia", "mimeType": "text/plain"},
  {"uri": "policy://devoluciones", "name": "Politica de devoluciones", "mimeType": "text/plain"},
  {"uri": "catalog://productos", "name": "Catalogo completo de productos", "mimeType": "application/json"}
]
```

`resources/read` request/response for `policy://envio`:

```json
{"jsonrpc": "2.0", "id": 4, "method": "resources/read", "params": {"uri": "policy://envio"}}
```

```json
{"jsonrpc": "2.0", "id": 4, "result": {"contents": [{"uri": "policy://envio", "mimeType": "text/plain", "text": "Envios en 2-5 dias habiles a nivel nacional. Envio gratis en compras mayores a Q500."}]}}
```

`resources/read` request/response for `catalog://productos` (the JSON is the `text` field's
value, `json.dumps`-encoded — MCP resource contents are always transmitted as a string,
whether they hold prose or serialized structured data):

```json
{"jsonrpc": "2.0", "id": 5, "method": "resources/read", "params": {"uri": "catalog://productos"}}
```

```json
{"jsonrpc": "2.0", "id": 5, "result": {"contents": [{"uri": "catalog://productos", "mimeType": "application/json", "text": "[{\"sku\": \"CAM-001\", \"nombre\": \"Camisa de vestir azul\", \"precio\": 249.0, \"descripcion\": \"Camisa de vestir de algodon, corte slim.\"}, ...]"}]}}
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

## Remote deployment (Google Cloud Run)

The exact same `handle_message` JSON-RPC logic also runs standalone over HTTP
(`backend/mcp_server_sales/core/http_server.py`, stdlib `http.server` only, no MCP SDK), a
single `POST /rpc` endpoint that accepts the same JSON-RPC request bodies shown throughout
this document and returns the same response bodies — the transport changes, the protocol
doesn't.

- **Image**: `deploy/cloud-run/Dockerfile` (build context: `backend/`). The server has no
  third-party dependencies (stdlib only), so the image installs nothing beyond the base
  Python image.
- **Endpoint**: deployed to Cloud Run at
  `https://mcp-server-sales-715967091740.us-central1.run.app/rpc` (project
  `proyecto1-redes-mcp`, region `us-central1`), reachable unauthenticated
  (`--allow-unauthenticated`) — acceptable for this course project's scope, but note this
  means anyone with the URL can call it; a production deployment would put an API key or
  IAM-based auth in front of it.
- **Client side**: `backend/app/main.py:connect_sales_mcp_server` picks the transport based
  on the `SALES_MCP_URL` environment variable — unset, it launches the local subprocess over
  stdio (`app/mcp_client/transports/stdio.py`); set to the Cloud Run URL above, it uses
  `app/mcp_client/transports/http.py`'s `HttpTransport` instead. Same `MCPClient`, same
  tools/prompts/resources, only the wire transport differs — this is what section 3.1.6 of
  the assignment asks for ("el chatbot debe hacer uso del servidor MCP remoto tal y como
  utiliza el servidor local").

Redeploy after a code change:

```bash
docker build -f deploy/cloud-run/Dockerfile -t mcp-server-sales:local backend
docker tag mcp-server-sales:local us-central1-docker.pkg.dev/proyecto1-redes-mcp/mcp-servers/mcp-server-sales:latest
docker push us-central1-docker.pkg.dev/proyecto1-redes-mcp/mcp-servers/mcp-server-sales:latest
gcloud run deploy mcp-server-sales \
  --image us-central1-docker.pkg.dev/proyecto1-redes-mcp/mcp-servers/mcp-server-sales:latest \
  --region us-central1 --allow-unauthenticated --port 8080 --project=proyecto1-redes-mcp
```

Run the chatbot against the remote server instead of the local subprocess:

```bash
export SALES_MCP_URL=https://mcp-server-sales-715967091740.us-central1.run.app   # Linux/macOS
set SALES_MCP_URL=https://mcp-server-sales-715967091740.us-central1.run.app      # Windows (cmd)
cd backend
python -m app.main
```

Verified for real (not just unit-tested) against the live deployment: `curl -X POST
.../rpc` for `initialize` and `tools/call`, and a direct run of
`app.main.connect_sales_mcp_server` using the real `MCPClient`/`HttpTransport` — both
returned correct results from the deployed container.

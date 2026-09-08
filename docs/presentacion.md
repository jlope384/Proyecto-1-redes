# Guion de presentación — Proyecto 1 (MCP Chatbot)

Esquema para la entrega oral (CC3067, sección 3.3 del enunciado: características
implementadas, dificultades, lecciones aprendidas). Pensado para presentarse haciendo la
demo en vivo desde el navegador (`backend/`, `python -m app.web`, abrir
`http://127.0.0.1:8000/`), no con slides estáticas. La terminal (`python -m app.main`) sigue
funcionando igual y es el respaldo si el navegador falla o si preguntan específicamente por la
UI de terminal (extra credit) — ver el punto 0 y la nota al final de la sección 1.

## 0. Antes de presentar (checklist de 2 minutos)

- [ ] Ollama corriendo (`ollama list` muestra `qwen2.5:7b`).
- [ ] `cd backend && .venv\Scripts\activate` (o `.venv/bin/activate` en Linux/Mac).
- [ ] Limpiar el workspace de demo si quieres una corrida "fresca":
      borrar `backend/workspace/demo-repo` y `backend/workspace/*.md` (está en
      `.gitignore`, no afecta el repo del proyecto).
- [ ] Arrancar `python -m app.web` y confirmar `http://127.0.0.1:8000/` carga y que el header
      muestra `Model: qwen2.5:7b | MCP servers: sales, filesystem, git` (tarda ~10-15s en
      arrancar la primera vez mientras `npx`/`uvx` lanzan los servidores oficiales — arráncalo
      con tiempo antes de presentar, no en vivo frente a la audiencia).
- [ ] Ten también una terminal con `python -m app.main` lista como respaldo (mismo backend,
      mismo comportamiento) por si el navegador da problemas, y para mostrar la UI de terminal
      si preguntan puntualmente por el extra credit.
- [ ] Decidir si la demo del servidor remoto se hace con `SALES_MCP_URL` seteado
      (Cloud Run real) o sin setear (subproceso local) — recomendado: mostrar ambas,
      primero local, luego exportar la variable y repetir una pregunta para que se note
      que la respuesta es idéntica aunque el servidor ahora está en la nube.
- [ ] Tener a mano `docs/wireshark/mcp_remote_capture.pcapng` +
      `docs/wireshark/tls_keylog.log` abiertos en Wireshark (Preferences → Protocols →
      TLS → cargar el keylog) por si preguntan por la captura en vivo.

## 1. Características implementadas (mapeado a la rúbrica)

**Funcionamiento general del chatbot (10%)**
- Conexión a un LLM vía su API (Ollama `/api/chat`, sin SDK) — preguntar algo genérico
  ("¿Quién fue Alan Turing?").
- Contexto de sesión — pregunta de seguimiento ("¿En qué fecha nació?") para mostrar que
  resuelve la referencia.
- Log de interacciones — `python -m app.main --show-log` al final, muestra cada
  request/response con el LLM y los servidores MCP.

**Servidores MCP — primera parte (30%)**
- Filesystem + Git MCP oficiales (Anthropic): pedir "crea un README, agrégalo al repo y
  haz un commit" — dispara `write_file` → `git_add` → `git_commit` reales sobre
  `backend/workspace/demo-repo/`. Cerrar mostrando `git log` en esa carpeta como prueba.
- Servidor propio (`mcp_server_sales`, caso de uso: asistente de ventas de una tienda de
  ropa): "¿Tienen camisas azules y cuánto cuestan?" → tool-calling real
  (`buscar_productos`). Mencionar que la especificación completa está en
  `docs/spec/mcp_server_sales.md`.

**Servidores MCP — segunda parte (50%)**
- Mismo servidor corriendo remoto en Google Cloud Run
  (`mcp-server-sales-715967091740.us-central1.run.app`): exportar `SALES_MCP_URL` y
  repetir una pregunta — mismo comportamiento, transporte HTTP en vez de stdio local.
- Captura de Wireshark contra ese servidor remoto: mostrar la tabla de clasificación de
  mensajes JSON-RPC (sync/request/response) de `docs/report/informe.md` sección 9, y
  opcionalmente el pcap descifrado en vivo si hay tiempo.

**Extra (15%): UI** — el enunciado da el 15% por una UI "en terminal o Web", no acumulable;
este proyecto tiene ambas con la misma lógica por debajo y la misma convención de colores
(cian=usuario, verde=respuesta del bot, amarillo tenue=actividad de tools en segundo plano,
rojo=errores, azul=info del sistema). La demo en vivo se hace en la UI Web
(`python -m app.web`, `http://127.0.0.1:8000/`) — mismo backend, misma sesión, mismos
servidores MCP que la terminal, solo cambia la capa de presentación
(`backend/app/web/api.py` reutiliza `run_turn` de `app/main.py` tal cual). Si preguntan
específicamente por la UI de terminal (la que se implementó primero), se puede mostrar con
`python -m app.main` — mismo comportamiento, señalar el spinner de "Thinking..." mientras
responde el LLM.

## 2. Dificultades (y cómo se resolvieron)

Usar esto como guion narrado, no lista técnica — la idea es mostrar que hubo problemas
reales y se debuggearon con evidencia, no que "todo funcionó a la primera":

1. **Robustez ante entradas no confiables.** La mayoría de bugs reales del proyecto no
   fueron de lógica de negocio sino de no validar entradas: un tool_call del LLM sin la
   forma esperada, un `arguments: null` explícito, una respuesta de un servidor oficial
   de terceros sin el campo asumido. Se trató tanto al LLM como a los servidores
   filesystem/git como fuentes no confiables, igual que a la entrada de un usuario.
2. **Portabilidad a Windows.** Todo el desarrollo iterativo se hizo en un sandbox Linux;
   al correr por primera vez en la máquina real (Windows, la de esta entrega),
   `subprocess.Popen(["npx", ...])` fallaba porque `npx`/`uvx` son shims `.cmd` que
   `CreateProcess` no puede ejecutar directo. Se resolvió con `shutil.which()` antes de
   lanzar el subproceso. Ningún test unitario lo había atrapado — solo correr en la
   máquina real lo reveló.
3. **Un modelo local chico se confunde con rutas.** El escenario filesystem+git fallaba
   de forma intermitente con `qwen2.5:7b`: escribía el README fuera del repo, o
   alucinaba una ruta absoluta casi correcta para `git_add`. Se resolvió dándole al LLM,
   en el system prompt, la ruta exacta a copiar literal en vez de describirla en prosa.
   Lección: un modelo local pequeño necesita instrucciones más explícitas que uno grande.
4. **Ver el tráfico real de un servidor HTTPS.** Cloud Run solo sirve HTTPS, así que
   Wireshark solo mostraba "TLS Application Data" cifrado. Se resolvió con
   `SSLKEYLOGFILE` (ya soportado nativamente por `requests`/`urllib3`, sin tocar código)
   para poder decir con evidencia real qué mensaje era el `initialize`, cuál el
   `tools/call`, etc.

## 3. Lecciones aprendidas

- MCP resuelve un problema real de interoperabilidad (function-calling estandarizado
  entre proveedores de LLM), no es solo una capa de más — implementarlo a mano (sin SDK)
  deja ver que esa interoperabilidad depende de detalles muy concretos de JSON-RPC (el
  `id` para correlacionar petición/respuesta, la ausencia de `id` en notificaciones,
  códigos de error estándar).
- Separar la lógica del protocolo (`core/server.py`) del transporte
  (`transports/stdio.py`, `transports/http.py`) fue la decisión de diseño que más rindió:
  permitió correr el mismo servidor local y remoto, y agregar HTTP sin tocar ni un
  archivo de `tools/`, `resources/` o `prompts/`.
- Los tests automatizados (133 en total) dan confianza en la lógica, pero no reemplazan
  correr el sistema real, con el LLM real, en el sistema operativo real de la entrega —
  los dos bugs más interesantes del proyecto (Windows, y el LLM chico confundiendo rutas)
  solo aparecieron ahí, no en ningún test.
- La capa de transporte HTTP elegida (una llamada nueva a `requests.post` por mensaje,
  sin reusar `Session`) es correcta pero no óptima — se nota con claridad en la captura de
  Wireshark (un handshake TCP+TLS completo por cada llamada JSON-RPC). Queda anotado como
  mejora futura en `docs/progress.md`, no se cambió para no tocar código ya verificado.

## 4. Preguntas esperables (y respuesta corta)

- **"¿Por qué no usaron FastMCP/un SDK de MCP?"** → El enunciado lo prohíbe
  explícitamente; todo el framing JSON-RPC (`handle_message`, el cliente en
  `app/mcp_client/`) está escrito a mano.
- **"¿Cómo se aseguran de que el LLM no invente resultados?"** → El LLM nunca ejecuta la
  acción: el host (`app/main.py`) intercepta la intención de tool-call, la ejecuta contra
  el servidor MCP real, y le devuelve el resultado real como mensaje `role: tool` — la
  respuesta final del LLM está grounded en ese dato real, no en su conocimiento previo.
- **"¿Qué pasa si un servidor MCP se cae a la mitad?"** → `handle_tool_calls` atrapa
  `MCPProtocolError`/`ConnectionError` por llamada y sigue la sesión, reportando un
  `[error]` en vez de crashear todo el chatbot (se puede demostrar matando el proceso del
  servidor de ventas a mitad de conversación).

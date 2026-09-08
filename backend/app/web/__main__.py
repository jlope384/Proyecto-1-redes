"""Run the web chatbot host: `python -m app.web` (serves the API and `frontend/public/` on
one origin - no CORS needed - defaulting to http://127.0.0.1:8000)."""
import os

import uvicorn

if __name__ == "__main__":
    host = os.environ.get("WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("WEB_PORT", "8000"))
    uvicorn.run("app.web.api:app", host=host, port=port)

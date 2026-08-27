"""Full product catalog exposed as a single JSON MCP resource.

Unlike the policy resources (plain text), this one demonstrates a non-text
`mimeType`: the contents are a JSON-encoded string, so a client that cares can
tell it apart from prose and parse it instead of just displaying it.
"""
import json

from mcp_server_sales.data.catalog import PRODUCTS

CATALOG_URI = "catalog://productos"


def list_resources():
    return [
        {
            "uri": CATALOG_URI,
            "name": "Catalogo completo de productos",
            "mimeType": "application/json",
        }
    ]


def read_resource(uri):
    if uri != CATALOG_URI:
        raise ValueError(f"Recurso desconocido: {uri}")
    return [
        {
            "uri": uri,
            "mimeType": "application/json",
            "text": json.dumps(PRODUCTS, ensure_ascii=False),
        }
    ]

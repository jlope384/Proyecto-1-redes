"""Static policy text exposed as MCP resources."""

POLICIES = {
    "policy://envio": {
        "name": "Politica de envio",
        "text": "Envios en 2-5 dias habiles a nivel nacional. Envio gratis en compras mayores a Q500.",
    },
    "policy://garantia": {
        "name": "Politica de garantia",
        "text": "Todos los productos tienen 90 dias de garantia contra defectos de fabricacion.",
    },
    "policy://devoluciones": {
        "name": "Politica de devoluciones",
        "text": "Devoluciones aceptadas hasta 30 dias despues de la compra, con etiqueta y sin uso.",
    },
}


def list_resources():
    return [{"uri": uri, "name": data["name"], "mimeType": "text/plain"} for uri, data in POLICIES.items()]


def read_resource(uri):
    if uri not in POLICIES:
        raise ValueError(f"Recurso desconocido: {uri}")
    data = POLICIES[uri]
    return [{"uri": uri, "mimeType": "text/plain", "text": data["text"]}]

"""Tool implementations for the sales MCP server. Pure functions over the mock catalog data."""
from mcp_server_sales.data.catalog import COMPLEMENTS, INVENTORY, ORDERS, PRODUCTS, find_product

TOOL_SPECS = [
    {
        "name": "buscar_productos",
        "description": "Busca productos del catalogo por nombre o descripcion.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "consultar_inventario",
        "description": "Consulta el stock disponible de un SKU por talla.",
        "inputSchema": {
            "type": "object",
            "properties": {"sku": {"type": "string"}},
            "required": ["sku"],
        },
    },
    {
        "name": "consultar_pedido",
        "description": "Consulta el estado de un pedido por su id.",
        "inputSchema": {
            "type": "object",
            "properties": {"pedido_id": {"type": "string"}},
            "required": ["pedido_id"],
        },
    },
    {
        "name": "recomendar_complementos",
        "description": "Recomienda productos que combinan con un SKU dado.",
        "inputSchema": {
            "type": "object",
            "properties": {"sku": {"type": "string"}},
            "required": ["sku"],
        },
    },
    {
        "name": "generar_enlace_de_pago",
        "description": "Genera un enlace de pago simulado para un SKU y cantidad, requiere confirmacion del cliente.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sku": {"type": "string"},
                "talla": {"type": "string"},
                "cantidad": {"type": "integer"},
            },
            "required": ["sku", "talla", "cantidad"],
        },
    },
]


def buscar_productos(query):
    words = query.lower().split()
    matches = []
    for p in PRODUCTS:
        haystack = f"{p['nombre']} {p['descripcion']}".lower()
        if all(word in haystack for word in words):
            matches.append(p)
    return matches


def consultar_inventario(sku):
    if sku not in INVENTORY:
        raise ValueError(f"SKU desconocido: {sku}")
    return {"sku": sku, "stock_por_talla": INVENTORY[sku]}


def consultar_pedido(pedido_id):
    order = ORDERS.get(pedido_id)
    if order is None:
        raise ValueError(f"Pedido desconocido: {pedido_id}")
    return {"pedido_id": pedido_id, **order}


def recomendar_complementos(sku):
    if find_product(sku) is None:
        raise ValueError(f"SKU desconocido: {sku}")
    skus = COMPLEMENTS.get(sku, [])
    return [find_product(s) for s in skus if find_product(s) is not None]


def generar_enlace_de_pago(sku, talla, cantidad):
    product = find_product(sku)
    if product is None:
        raise ValueError(f"SKU desconocido: {sku}")
    stock = INVENTORY.get(sku, {}).get(talla, 0)
    if cantidad > stock:
        raise ValueError(f"Stock insuficiente para {sku} talla {talla}: hay {stock}, se pidieron {cantidad}")
    total = round(product["precio"] * cantidad, 2)
    return {
        "sku": sku,
        "talla": talla,
        "cantidad": cantidad,
        "total": total,
        "enlace_pago": f"https://pagos.tienda-demo.local/checkout/{sku}-{talla}-{cantidad}",
        "requiere_confirmacion_cliente": True,
    }


DISPATCH = {
    "buscar_productos": lambda args: buscar_productos(args["query"]),
    "consultar_inventario": lambda args: consultar_inventario(args["sku"]),
    "consultar_pedido": lambda args: consultar_pedido(args["pedido_id"]),
    "recomendar_complementos": lambda args: recomendar_complementos(args["sku"]),
    "generar_enlace_de_pago": lambda args: generar_enlace_de_pago(
        args["sku"], args["talla"], args["cantidad"]
    ),
}

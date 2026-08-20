"""In-memory mock data for the sales MCP server (catalog, inventory, orders)."""

PRODUCTS = [
    {
        "sku": "CAM-001",
        "nombre": "Camisa de vestir azul",
        "precio": 249.00,
        "descripcion": "Camisa de vestir de algodon, corte slim.",
    },
    {
        "sku": "PAN-002",
        "nombre": "Pantalon casual negro",
        "precio": 329.00,
        "descripcion": "Pantalon de corte recto, tela stretch.",
    },
    {
        "sku": "COR-003",
        "nombre": "Corbata de seda roja",
        "precio": 149.00,
        "descripcion": "Corbata de seda, ancho clasico.",
    },
    {
        "sku": "CIN-004",
        "nombre": "Cinturon de cuero cafe",
        "precio": 179.00,
        "descripcion": "Cinturon de cuero genuino, hebilla plateada.",
    },
]

INVENTORY = {
    "CAM-001": {"S": 5, "M": 12, "L": 8, "XL": 0},
    "PAN-002": {"30": 3, "32": 10, "34": 6, "36": 0},
    "COR-003": {"UNICA": 20},
    "CIN-004": {"UNICA": 0},
}

ORDERS = {
    "PED-1001": {
        "estado": "enviado",
        "items": [{"sku": "CAM-001", "talla": "M", "cantidad": 1}],
        "total": 249.00,
    },
    "PED-1002": {
        "estado": "en preparacion",
        "items": [{"sku": "PAN-002", "talla": "32", "cantidad": 2}],
        "total": 658.00,
    },
}

COMPLEMENTS = {
    "CAM-001": ["COR-003", "CIN-004"],
    "PAN-002": ["CIN-004"],
    "COR-003": ["CAM-001"],
    "CIN-004": ["PAN-002"],
}


def find_product(sku):
    return next((p for p in PRODUCTS if p["sku"] == sku), None)

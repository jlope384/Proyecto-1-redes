"""MCP prompt templates for the sales server: reusable, parameterized starting points for a
chat turn (the `prompts/*` half of the MCP spec, distinct from `tools/*` and `resources/*`).
"""

PROMPT_SPECS = [
    {
        "name": "recomendar_outfit",
        "description": "Arma una recomendacion de outfit completo para una ocasion, usando el catalogo.",
        "arguments": [
            {"name": "ocasion", "description": "Ocasion o evento (ej. entrevista de trabajo)", "required": True},
            {"name": "presupuesto", "description": "Presupuesto maximo en quetzales", "required": False},
        ],
    },
    {
        "name": "resumen_pedido",
        "description": "Pide un resumen amigable del estado de un pedido para el cliente.",
        "arguments": [
            {"name": "pedido_id", "description": "Id del pedido a consultar", "required": True},
        ],
    },
]

PROMPT_SPECS_BY_NAME = {spec["name"]: spec for spec in PROMPT_SPECS}


def _missing_required_arguments(name, arguments):
    required = [arg["name"] for arg in PROMPT_SPECS_BY_NAME[name]["arguments"] if arg["required"]]
    return [field for field in required if field not in arguments]


def _text_message(role, text):
    return {"role": role, "content": {"type": "text", "text": text}}


def _recomendar_outfit(arguments):
    ocasion = arguments["ocasion"]
    presupuesto = arguments.get("presupuesto")
    text = (
        f"Recomienda un outfit completo (prenda principal + al menos un complemento) para "
        f"la ocasion: {ocasion}. Usa buscar_productos y recomendar_complementos para elegir "
        "productos reales del catalogo, no inventes SKUs."
    )
    if presupuesto:
        text += f" El total no debe superar Q{presupuesto}."
    return "Eres un asesor de imagen de la tienda.", [_text_message("user", text)]


def _resumen_pedido(arguments):
    pedido_id = arguments["pedido_id"]
    text = (
        f"Consulta el pedido {pedido_id} con consultar_pedido y resume su estado, articulos "
        "y total en un tono breve y amigable para el cliente."
    )
    return "Eres un agente de servicio al cliente.", [_text_message("user", text)]


_BUILDERS = {
    "recomendar_outfit": _recomendar_outfit,
    "resumen_pedido": _resumen_pedido,
}


def list_prompts():
    return PROMPT_SPECS


def get_prompt(name, arguments):
    try:
        known_prompt = name in PROMPT_SPECS_BY_NAME
    except TypeError:
        # Same unhashable-value crash class as tools/call's "name" and resources/read's
        # "uri": a JSON array/object instead of a string makes `name in {...}` raise
        # TypeError instead of just failing to match. Treat it as an unknown prompt.
        known_prompt = False
    if not known_prompt:
        raise ValueError(f"Prompt desconocido: {name}")
    try:
        missing = _missing_required_arguments(name, arguments)
        if missing:
            raise ValueError(f"Faltan argumentos requeridos para {name}: {', '.join(missing)}")
        description, messages = _BUILDERS[name](arguments)
    except (TypeError, KeyError, AttributeError) as exc:
        # Defensive net mirroring tools/call's: `arguments` being a list/int/etc instead of a
        # dict (e.g. a malformed prompts/get request) must not crash the whole server subprocess.
        raise ValueError(f"Argumentos invalidos para {name}: {exc}") from exc
    return {"description": description, "messages": messages}

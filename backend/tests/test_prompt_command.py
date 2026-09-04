from app.main import parse_prompt_command, prompt_text


def test_parse_prompt_command_with_key_value_arguments():
    result = parse_prompt_command("/prompt resumen_pedido pedido_id=PED-1001")

    assert result == ("resumen_pedido", {"pedido_id": "PED-1001"})


def test_parse_prompt_command_with_no_arguments():
    result = parse_prompt_command("/prompt resumen_pedido")

    assert result == ("resumen_pedido", {})


def test_parse_prompt_command_with_multiple_arguments():
    result = parse_prompt_command("/prompt recomendar_outfit ocasion=boda presupuesto=500")

    assert result == ("recomendar_outfit", {"ocasion": "boda", "presupuesto": "500"})


def test_parse_prompt_command_ignores_malformed_pair():
    result = parse_prompt_command("/prompt resumen_pedido not-a-pair")

    assert result == ("resumen_pedido", {})


def test_parse_prompt_command_returns_none_for_plain_message():
    assert parse_prompt_command("cuanto cuesta la camisa azul?") is None


def test_parse_prompt_command_returns_none_for_bare_slash_prompt():
    assert parse_prompt_command("/prompt") is None


def test_parse_prompt_command_returns_none_for_message_merely_starting_with_prompt():
    # A plain startswith("/prompt") check used to misparse this as the command name "prompted",
    # silently swallowing the rest of the user's actual message.
    assert parse_prompt_command("/prompted the wrong SKU, can you check?") is None


def test_prompt_text_joins_message_contents():
    result = prompt_text({"description": "d", "messages": [{"role": "user", "content": {"type": "text", "text": "hola"}}]})

    assert result == "hola"


def test_prompt_text_joins_multiple_messages_with_newline():
    result = prompt_text(
        {
            "messages": [
                {"role": "assistant", "content": {"type": "text", "text": "primero"}},
                {"role": "user", "content": {"type": "text", "text": "segundo"}},
            ]
        }
    )

    assert result == "primero\nsegundo"

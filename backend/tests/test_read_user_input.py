import app.main as main


def test_read_user_input_returns_the_typed_text(monkeypatch):
    monkeypatch.setattr(main, "render_user_prompt", lambda: "hola")

    assert main.read_user_input() == "hola"


def test_read_user_input_returns_none_on_eof(monkeypatch):
    def raise_eof():
        raise EOFError

    monkeypatch.setattr(main, "render_user_prompt", raise_eof)

    assert main.read_user_input() is None


def test_read_user_input_returns_none_on_keyboard_interrupt(monkeypatch):
    def raise_interrupt():
        raise KeyboardInterrupt

    monkeypatch.setattr(main, "render_user_prompt", raise_interrupt)

    assert main.read_user_input() is None

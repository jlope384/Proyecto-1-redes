"""Interactive command-line chatbot host: connects to Ollama and keeps session context."""
from app.chat.session import ChatSession
from app.llm.ollama_client import OllamaClient, OllamaConnectionError
from app.logging.interaction_logger import build_interaction_logger, log_interaction

SYSTEM_PROMPT = "You are a helpful assistant."


def run():
    client = OllamaClient()
    session = ChatSession(system_prompt=SYSTEM_PROMPT)
    logger = build_interaction_logger()

    print(f"Connected to Ollama model '{client.model}'. Type 'exit' to quit.")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break
        if not user_input:
            continue

        session.add_user_message(user_input)
        log_interaction(logger, "llm", "request", session.history())

        try:
            reply = client.chat(session.history())
        except OllamaConnectionError as exc:
            print(f"[error] {exc}")
            session.drop_last()
            continue

        log_interaction(logger, "llm", "response", {"role": "assistant", "content": reply})
        session.add_assistant_message(reply)
        print(f"Bot: {reply}")


if __name__ == "__main__":
    run()

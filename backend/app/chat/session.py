"""In-memory conversation session that keeps message history for context."""


class ChatSession:
    def __init__(self, system_prompt=None):
        self.messages = []
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})

    def add_user_message(self, content):
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content):
        self.messages.append({"role": "assistant", "content": content})

    def drop_last(self):
        if self.messages:
            self.messages.pop()

    def history(self):
        return list(self.messages)

"""In-memory conversation session that keeps message history for context."""


class ChatSession:
    def __init__(self, system_prompt=None):
        self.messages = []
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})

    def add_user_message(self, content):
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content, tool_calls=None):
        message = {"role": "assistant", "content": content}
        if tool_calls:
            message["tool_calls"] = tool_calls
        self.messages.append(message)

    def add_tool_result(self, tool_name, content):
        self.messages.append({"role": "tool", "name": tool_name, "content": content})

    def drop_last(self):
        if self.messages:
            self.messages.pop()

    def history(self):
        return list(self.messages)

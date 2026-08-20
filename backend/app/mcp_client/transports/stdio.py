"""Stdio transport: launches an MCP server as a subprocess and exchanges newline-delimited
JSON-RPC messages over its stdin/stdout, per the MCP stdio transport spec.
"""
import json
import subprocess


class StdioTransport:
    def __init__(self, command, args=None, cwd=None):
        self.process = subprocess.Popen(
            [command, *(args or [])],
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )

    def send(self, message):
        line = json.dumps(message, ensure_ascii=False)
        self.process.stdin.write(line + "\n")
        self.process.stdin.flush()

    def receive(self):
        line = self.process.stdout.readline()
        if line == "":
            stderr = self.process.stderr.read()
            raise ConnectionError(f"MCP server closed stdout unexpectedly. stderr: {stderr}")
        return json.loads(line)

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            self.process.terminate()
            self.process.wait(timeout=5)

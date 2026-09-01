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
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise ConnectionError(f"MCP server sent a non-JSON line on stdout: {line!r} ({exc})") from exc

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # The server ignored terminate() (e.g. still starting up) - kill it so a
                # single slow/hung subprocess can't stop the other connected servers
                # (sales/filesystem/git) from being closed too by the caller's cleanup loop.
                self.process.kill()
                self.process.wait()

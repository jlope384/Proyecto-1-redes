"""Stdio transport: launches an MCP server as a subprocess and exchanges newline-delimited
JSON-RPC messages over its stdin/stdout, per the MCP stdio transport spec.
"""
import json
import queue
import shutil
import subprocess
import threading

# `Popen.stdout.readline()` has no native way to time out on POSIX (a pipe fd isn't
# select()-able the same way on Windows, which is the platform this project is actually
# demoed on - see StdioTransport.__init__'s shutil.which comment), so a hung server
# subprocess (stuck processing a request, or one that never replies) would otherwise block
# receive() forever with no way to recover - the host's own KeyboardInterrupt handling in
# app/main.py only helps a human who is present to press Ctrl+C, and the web host
# (app/web/api.py) has no such escape hatch at all. DEFAULT_TIMEOUT bounds that wait.
DEFAULT_TIMEOUT = 30.0


class StdioTransport:
    def __init__(self, command, args=None, cwd=None, timeout=DEFAULT_TIMEOUT):
        # On Windows, commands like `npx`/`uvx` resolve to a `.cmd`/`.bat` shim that
        # CreateProcess can't exec directly without a shell. shutil.which() resolves the
        # PATHEXT-aware full path on Windows and is a harmless no-op lookup on POSIX.
        resolved_command = shutil.which(command) or command
        self.timeout = timeout
        self.process = subprocess.Popen(
            [resolved_command, *(args or [])],
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
        line = self._readline_with_timeout()
        if line == "":
            stderr = self.process.stderr.read()
            raise ConnectionError(f"MCP server closed stdout unexpectedly. stderr: {stderr}")
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise ConnectionError(f"MCP server sent a non-JSON line on stdout: {line!r} ({exc})") from exc

    def _readline_with_timeout(self):
        # A dedicated thread per call, rather than one long-lived reader thread, because
        # readline() has no cancel/interrupt mechanism - on a timeout the thread is simply
        # abandoned (daemon, so it never blocks process exit) and either eventually reads
        # the late reply harmlessly (nobody consumes it) or unblocks with "" once the
        # subprocess is closed/killed by the caller.
        result = queue.Queue(maxsize=1)
        reader = threading.Thread(target=lambda: result.put(self.process.stdout.readline()), daemon=True)
        reader.start()
        try:
            return result.get(timeout=self.timeout)
        except queue.Empty:
            raise ConnectionError(
                f"Timed out after {self.timeout}s waiting for a response from the MCP server "
                "subprocess (it may be hung)"
            )

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

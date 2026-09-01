from app.main import connect_mcp_servers


class FakeClient:
    def __init__(self, name):
        self.name = name
        self.closed = False

    def close(self):
        self.closed = True


def test_connect_mcp_servers_returns_all_clients_in_order():
    clients = connect_mcp_servers([lambda: FakeClient("a"), lambda: FakeClient("b")])

    assert [c.name for c in clients] == ["a", "b"]


def test_connect_mcp_servers_closes_already_connected_clients_on_a_later_failure():
    # Simulates: the sales and filesystem servers start fine, but the git server's
    # initialize() fails - the two already-spawned subprocesses must not leak.
    connected = []

    def make_connector(name, should_fail=False):
        def connector():
            if should_fail:
                raise ConnectionError(f"{name} failed to start")
            client = FakeClient(name)
            connected.append(client)
            return client

        return connector

    try:
        connect_mcp_servers(
            [
                make_connector("sales"),
                make_connector("filesystem"),
                make_connector("git", should_fail=True),
            ]
        )
    except ConnectionError:
        pass
    else:
        assert False, "expected the git connector's ConnectionError to propagate"

    assert len(connected) == 2
    assert all(client.closed for client in connected)


def test_connect_mcp_servers_reraises_the_original_failure():
    def failing_connector():
        raise ValueError("boom")

    try:
        connect_mcp_servers([failing_connector])
    except ValueError as exc:
        assert str(exc) == "boom"
        return
    assert False, "expected ValueError to propagate"

"""Tests du lanceur de production api/serve.py."""
import socket

import api.serve as serve


class FakeSocket:
    def __init__(self):
        self.options = {}

    def setsockopt(self, level, option, value):
        self.options[(level, option)] = value


def test_single_worker_runs_plain_server(monkeypatch):
    calls = []
    monkeypatch.setenv("WEB_CONCURRENCY", "1")
    monkeypatch.setattr(serve.uvicorn.Server, "run", lambda self, *a, **k: calls.append(self.config))
    serve.main()
    assert len(calls) == 1
    assert calls[0].access_log is False
    assert calls[0].proxy_headers is True


def test_multi_worker_enables_tcp_nodelay(monkeypatch):
    fake_sock = FakeSocket()
    started = {}

    class FakeMultiprocess:
        def __init__(self, config, sockets):
            started["workers"] = config.workers
            started["sockets"] = sockets

        def run(self):
            started["run"] = True

    monkeypatch.setenv("WEB_CONCURRENCY", "4")
    monkeypatch.setattr(serve.uvicorn.Config, "bind_socket", lambda self: fake_sock)
    monkeypatch.setattr(serve, "Multiprocess", FakeMultiprocess)
    serve.main()

    assert started == {"workers": 4, "sockets": [fake_sock], "run": True}
    assert fake_sock.options[(socket.IPPROTO_TCP, socket.TCP_NODELAY)] == 1

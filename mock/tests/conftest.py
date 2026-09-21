import socket
import threading
import time

import pytest
import uvicorn
from fastapi.testclient import TestClient

from mock_server.app import app
from mock_server.state import STATE


@pytest.fixture(autouse=True)
def _reset_state():
    STATE.reset()
    yield
    STATE.reset()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(scope="session")
def live_url():
    """The app served by a real uvicorn on a free local port, for SDK compatibility tests."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("uvicorn did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)

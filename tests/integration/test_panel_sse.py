from __future__ import annotations

import socket
import threading
import time

import httpx
import pytest
import uvicorn

from tests.integration.app import create_app


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def gallery_server_url() -> str:
    port = _find_free_port()
    config = uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        try:
            httpx.get(f"{base_url}/", timeout=0.5)
            break
        except httpx.HTTPError:
            time.sleep(0.05)
    else:
        server.should_exit = True
        raise RuntimeError("gallery server did not become ready")
    yield base_url
    server.should_exit = True
    thread.join(timeout=3.0)


def test_gallery_page_includes_panel_sse_demo_markup(gallery_server_url: str) -> None:
    response = httpx.get(f"{gallery_server_url}/", timeout=5.0)
    response.raise_for_status()
    page_html = response.text
    assert "g-panel-sse-live" in page_html
    assert "/sse/panel-demo" in page_html
    assert "sse-connect" in page_html


def test_panel_sse_stream_emits_first_tick(gallery_server_url: str) -> None:
    with httpx.Client(timeout=httpx.Timeout(5.0, read=5.0)) as http_client:
        with http_client.stream("GET", f"{gallery_server_url}/sse/panel-demo") as response:
            response.raise_for_status()
            received = b""
            for chunk in response.iter_bytes():
                received += chunk
                if b"\n\n" in received:
                    break
    assert b"data:" in received
    assert b"1" in received

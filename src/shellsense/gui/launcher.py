"""Desktop native window launcher using pywebview and uvicorn.

Binds server exclusively to 127.0.0.1 on a dynamic free port, passes the
ephemeral session token directly through pywebview JS bridge, and opens the native UI.
"""

from __future__ import annotations

import secrets
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
import webview

from shellsense.api.app import create_app


def find_free_port() -> int:
    """Find a random available port on 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class JSBridge:
    """JS bridge exposed to the frontend window object."""

    def __init__(self, token: str, port: int) -> None:
        self._token = token
        self._port = port

    def get_session_token(self) -> str:
        """Return the in-memory ephemeral session token directly to frontend JS."""
        return self._token

    def get_api_port(self) -> int:
        return self._port


def launch_desktop(static_dir: Path | None = None) -> None:
    """Launch the ShellSense desktop application."""
    if static_dir is None:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            meipass_dist = Path(meipass) / "frontend" / "dist"
            if meipass_dist.exists():
                static_dir = meipass_dist
        if static_dir is None:
            repo_dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
            if repo_dist.exists():
                static_dir = repo_dist

    port = find_free_port()
    token = secrets.token_hex(32)

    app = create_app(session_token=token, port=port, static_dir=static_dir)

    # Start uvicorn on loopback in a background thread
    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    time.sleep(0.5)

    bridge = JSBridge(token=token, port=port)
    url = f"http://127.0.0.1:{port}"

    token_url = f"{url}/?token={token}"

    try:
        # Create pywebview native window
        webview.create_window(
            title="ShellSense",
            url=token_url,
            js_api=bridge,
            width=1200,
            height=800,
            min_size=(900, 600),
        )
        webview.start()
    except Exception as exc:
        print(f"pywebview native window unavailable ({exc}). Opening in default browser at {token_url}...")
        webbrowser.open(token_url)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    launch_desktop()

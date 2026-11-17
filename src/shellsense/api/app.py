"""FastAPI application factory and middleware configuration.

Mounts all routes under /api/v1, attaches security middleware,
and provides the WebSocket event stream.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from shellsense.api.events import GLOBAL_EVENT_HUB
from shellsense.api.routes import (
    chat,
    files,
    history,
    permissions,
    plans,
    processes,
    settings,
    system,
    tasks,
)
from shellsense.api.security import SecurityMiddleware, SessionSecurity


def create_app(
    session_token: str | None = None,
    port: int = 5173,
    static_dir: Path | None = None,
) -> FastAPI:
    """Create and configure the hardened FastAPI application."""
    app = FastAPI(
        title="ShellSense Local API",
        version="0.1.0",
        docs_url=None,  # Disabled for offline hardened security
        redoc_url=None,
    )

    security = SessionSecurity(token=session_token, port=port)
    app.add_middleware(SecurityMiddleware, security=security)

    # Mount REST routes under /api/v1
    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(plans.router, prefix="/api/v1")
    app.include_router(system.router, prefix="/api/v1")
    app.include_router(files.router, prefix="/api/v1")
    app.include_router(processes.router, prefix="/api/v1")
    app.include_router(tasks.router, prefix="/api/v1")
    app.include_router(history.router, prefix="/api/v1")
    app.include_router(settings.router, prefix="/api/v1")
    app.include_router(permissions.router, prefix="/api/v1")

    # WebSocket events endpoint
    @app.websocket("/api/v1/events")
    async def websocket_events(websocket: WebSocket):
        auth = websocket.headers.get("authorization")
        if not security.verify_token(auth):
            await websocket.close(code=1008)
            return

        await GLOBAL_EVENT_HUB.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
                # Handle client resume or ping
        except WebSocketDisconnect:
            await GLOBAL_EVENT_HUB.disconnect(websocket)

    # Custom index handlers injecting per-launch loopback token meta tag
    @app.get("/", response_class=HTMLResponse)
    @app.get("/index.html", response_class=HTMLResponse)
    async def get_index():
        if static_dir and static_dir.exists():
            index_path = static_dir / "index.html"
            if index_path.exists():
                content = index_path.read_text(encoding="utf-8")
                token_val = session_token or security.token
                token_tag = (
                    f'<meta name="shellsense-session-token" content="{token_val}">'
                    f'<meta name="shellsense-port" content="{port}">'
                )
                if "</head>" in content:
                    content = content.replace("</head>", f"{token_tag}</head>", 1)
                else:
                    content = f"{token_tag}{content}"
                return HTMLResponse(content=content)
        return HTMLResponse("<!doctype html><html><body><h1>ShellSense Backend Running</h1></body></html>")

    # Mount static frontend if available
    if static_dir and static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="frontend")

    return app

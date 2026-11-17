"""Tests for local API hardening: Host/Origin allowlist, session token, CSP headers."""

from pathlib import Path

from fastapi.testclient import TestClient

from shellsense.api.app import create_app


def test_api_requires_valid_session_token() -> None:
    token = "secret1234567890123456789012345678"
    app = create_app(session_token=token, port=5173)
    client = TestClient(app, base_url="http://127.0.0.1:5173")

    # 1. Missing token -> 401
    res_no_token = client.get("/api/v1/system/info")
    assert res_no_token.status_code == 401

    # 2. Invalid token -> 401
    res_bad_token = client.get(
        "/api/v1/system/info",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert res_bad_token.status_code == 401

    # 3. Valid token -> 200
    res_valid = client.get(
        "/api/v1/system/info",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_valid.status_code == 200
    assert "Content-Security-Policy" in res_valid.headers
    assert res_valid.headers["X-Content-Type-Options"] == "nosniff"


def test_api_rejects_foreign_host() -> None:
    token = "secret1234567890123456789012345678"
    app = create_app(session_token=token, port=5173)
    client = TestClient(app, base_url="http://127.0.0.1:5173")

    # Attempt DNS rebinding with evil host
    res = client.get(
        "/api/v1/system/info",
        headers={"Host": "attacker.com", "Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_api_rejects_foreign_origin_on_post() -> None:
    token = "secret1234567890123456789012345678"
    app = create_app(session_token=token, port=5173)
    client = TestClient(app, base_url="http://127.0.0.1:5173")

    # Cross-site POST attempt
    res = client.post(
        "/api/v1/chat/messages",
        json={"text": "Show RAM"},
        headers={"Origin": "http://evil-site.com", "Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_approve_endpoint_forbids_client_supplied_targets() -> None:
    token = "secret1234567890123456789012345678"
    app = create_app(session_token=token, port=5173)
    client = TestClient(app, base_url="http://127.0.0.1:5173")

    # Client attempts to smuggle extra fields into approval
    res = client.post(
        "/api/v1/plans/p-1/approve",
        json={"plan_hash": "somehash", "targets": ["/etc/passwd"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Extra fields forbidden by schema
    assert res.status_code == 422


def test_index_meta_tag_injection(tmp_path: Path) -> None:
    static_dir = tmp_path / "dist"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><html><head><title>Test</title></head><body>App</body></html>")

    token = "meta-test-token-12345"
    app = create_app(session_token=token, port=5173, static_dir=static_dir)
    client = TestClient(app, base_url="http://127.0.0.1:5173")

    res = client.get("/", headers={"Host": "127.0.0.1:5173"})
    assert res.status_code == 200
    assert 'meta name="shellsense-session-token" content="meta-test-token-12345"' in res.text
    assert 'meta name="shellsense-port" content="5173"' in res.text


def test_system_info_returns_real_user_and_cross_platform_disk() -> None:
    token = "sysinfo-token-1234567890"
    app = create_app(session_token=token, port=5173)
    client = TestClient(app, base_url="http://127.0.0.1:5173")

    res = client.get("/api/v1/system/info", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "user" in data
    assert len(data["user"]) > 0
    assert "os" in data
    assert "display_name" in data["os"]
    assert "sample" in data
    assert data["sample"]["ram_total_bytes"] > 0
    assert data["sample"]["disk_total_bytes"] > 0


def test_process_list_returns_real_processes() -> None:
    token = "proc-test-token-1234567890"
    app = create_app(session_token=token, port=5173)
    client = TestClient(app, base_url="http://127.0.0.1:5173")

    res = client.get("/api/v1/processes?limit=10", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "processes" in data
    assert len(data["processes"]) > 0
    first = data["processes"][0]
    assert "pid" in first
    assert "name" in first
    assert "can_terminate" in first

"""Comprehensive test suite for expanded operations, transparency, and context follow-up."""

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from shellsense.api.app import create_app
from shellsense.models import (
    Capability,
    ExecutionStatus,
    Intent,
    RiskLevel,
)
from shellsense.nlp.rule_based import DEFAULT_PARSER
from shellsense.operations import GLOBAL_REGISTRY
from shellsense.planner import Planner
from shellsense.safety.approval import DEFAULT_PLAN_STORE
from shellsense.safety.consent import PermissionGate


def setup_temp_environment() -> tuple[tempfile.TemporaryDirectory[str], Path, PermissionGate]:
    """Create a temporary sandbox directory with granted capabilities."""
    tmp = tempfile.TemporaryDirectory()
    sandbox = Path(tmp.name).resolve()

    gate = PermissionGate(config_dir=sandbox / ".config")
    gate.write_grant(
        capabilities=list(Capability),
        folder_roots=[str(sandbox)],
        force_tty_check=False,
    )
    return tmp, sandbox, gate


def test_transparency_api_chat_endpoint() -> None:
    token = "secret1234567890123456789012345678"
    app = create_app(session_token=token, port=5173)
    client = TestClient(app, base_url="http://127.0.0.1:5173")

    # Safe system memory query
    res = client.post(
        "/api/v1/chat/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "Show my RAM usage"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["kind"] == "result"
    assert "Understood as:" in data["understood_as"] or "Show Memory" in data["understood_as"]
    assert data["explanation"] is not None
    assert data["explanation"]["operation"] == "SHOW_MEMORY"
    assert data["explanation"]["confidence"] >= 0.85


def test_file_creation_and_append_operations() -> None:
    tmp, sandbox, gate = setup_temp_environment()
    planner = Planner(permission_gate=gate)

    try:
        # 1. CREATE_FOLDER
        new_dir = sandbox / "projects"
        intent_folder = Intent(
            operation="CREATE_FOLDER",
            params={"path": str(new_dir)},
            confidence=1.0,
            original_text="make a folder called projects",
        )
        plan_folder = planner.create_plan(intent_folder)
        assert plan_folder.risk_level == RiskLevel.MODIFY
        DEFAULT_PLAN_STORE.store_plan(plan_folder)
        approved_folder = DEFAULT_PLAN_STORE.approve_plan(plan_folder.plan_id, plan_folder.plan_hash)
        op_folder = GLOBAL_REGISTRY.get_by_intent("CREATE_FOLDER")
        assert op_folder is not None
        res_folder = op_folder.execute(approved_folder)
        assert res_folder.status == ExecutionStatus.SUCCESS
        assert new_dir.is_dir()

        # 2. CREATE_FILE
        target_file = new_dir / "notes.txt"
        intent_file = Intent(
            operation="CREATE_FILE",
            params={"path": str(target_file), "content": "Line 1\n"},
            confidence=1.0,
            original_text="create a file notes.txt with Line 1",
        )
        plan_file = planner.create_plan(intent_file)
        DEFAULT_PLAN_STORE.store_plan(plan_file)
        approved_file = DEFAULT_PLAN_STORE.approve_plan(plan_file.plan_id, plan_file.plan_hash)
        op_file = GLOBAL_REGISTRY.get_by_intent("CREATE_FILE")
        assert op_file is not None
        res_file = op_file.execute(approved_file)
        assert res_file.status == ExecutionStatus.SUCCESS
        assert target_file.is_file()
        assert target_file.read_text(encoding="utf-8") == "Line 1\n"

        # 3. APPEND_TEXT
        intent_append = Intent(
            operation="APPEND_TEXT",
            params={"path": str(target_file), "content": "Line 2\n"},
            confidence=1.0,
            original_text="add Line 2 to notes.txt",
        )
        plan_append = planner.create_plan(intent_append)
        DEFAULT_PLAN_STORE.store_plan(plan_append)
        approved_append = DEFAULT_PLAN_STORE.approve_plan(plan_append.plan_id, plan_append.plan_hash)
        op_append = GLOBAL_REGISTRY.get_by_intent("APPEND_TEXT")
        assert op_append is not None
        res_append = op_append.execute(approved_append)
        assert res_append.status == ExecutionStatus.SUCCESS
        assert target_file.read_text(encoding="utf-8") == "Line 1\nLine 2\n"
    finally:
        tmp.cleanup()


def test_file_retrieval_and_context_followup() -> None:
    tmp, sandbox, gate = setup_temp_environment()
    planner = Planner(permission_gate=gate)

    try:
        # Create test files
        f1 = sandbox / "report_big.pdf"
        f1.write_bytes(b"A" * 10000)
        f2 = sandbox / "notes_small.txt"
        f2.write_bytes(b"B" * 100)
        f3 = sandbox / "image.png"
        f3.write_bytes(b"C" * 500)

        # 1. LARGEST_FILES (SAFE)
        intent_large = Intent(
            operation="LARGEST_FILES",
            params={"path": str(sandbox), "count": 5},
            confidence=0.95,
            original_text="find the largest files in sandbox",
        )
        plan_large = planner.create_plan(intent_large)
        assert plan_large.risk_level == RiskLevel.SAFE
        DEFAULT_PLAN_STORE.store_plan(plan_large)
        approved_large = DEFAULT_PLAN_STORE.approve_plan(plan_large.plan_id, plan_large.plan_hash)
        op_retrieval = GLOBAL_REGISTRY.get_by_intent("LARGEST_FILES")
        assert op_retrieval is not None
        res_large = op_retrieval.execute(approved_large)
        assert res_large.status == ExecutionStatus.SUCCESS
        assert "report_big.pdf" in res_large.outcomes[0].message

        # 2. Context Follow-Up: "delete them"
        parsed_followup = DEFAULT_PARSER.parse("delete them", session_id="default")
        assert isinstance(parsed_followup, Intent)
        assert parsed_followup.operation == "TRASH_FILES"
        assert len(parsed_followup.params.get("targets", [])) >= 2
    finally:
        tmp.cleanup()


def test_meta_operations_execution() -> None:
    tmp, sandbox, gate = setup_temp_environment()
    planner = Planner(permission_gate=gate)

    try:
        for meta_intent_name in ["HELP", "SHOW_PERMISSIONS", "SHOW_HISTORY", "SHOW_TASKS"]:
            intent = Intent(
                operation=meta_intent_name,
                params={},
                confidence=1.0,
                original_text=f"test {meta_intent_name}",
            )
            plan = planner.create_plan(intent)
            assert plan.risk_level == RiskLevel.SAFE
            DEFAULT_PLAN_STORE.store_plan(plan)
            approved = DEFAULT_PLAN_STORE.approve_plan(plan.plan_id, plan.plan_hash)
            op = GLOBAL_REGISTRY.get_by_intent(meta_intent_name)
            assert op is not None
            res = op.execute(approved)
            assert res.status == ExecutionStatus.SUCCESS
            assert len(res.outcomes) > 0
    finally:
        tmp.cleanup()

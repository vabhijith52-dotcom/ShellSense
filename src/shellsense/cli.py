"""Command-line interface adapter for ShellSense.

Allows inspection and management of capabilities, natural language queries, and desktop GUI launch.
Adheres to Invariant 3 (no root/admin) and Invariant 13 (live human TTY check).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from shellsense.executor.executor import DEFAULT_EXECUTOR
from shellsense.gui.launcher import launch_desktop
from shellsense.models import Capability, RiskLevel
from shellsense.nlp.rule_based import DEFAULT_PARSER
from shellsense.nlp.schemas import Clarification, Refusal
from shellsense.planner import DEFAULT_PLANNER
from shellsense.platform import get_platform_adapter
from shellsense.safety.approval import DEFAULT_PLAN_STORE
from shellsense.safety.consent import PermissionGate
from shellsense.storage.audit import DEFAULT_AUDIT_LOGGER, AuditDecision


def handle_ask(query: str) -> int:
    """Process a natural language query through the safety pipeline via CLI."""
    parsed = DEFAULT_PARSER.parse(query)

    if isinstance(parsed, Refusal):
        DEFAULT_AUDIT_LOGGER.log(
            session_id="cli",
            original_text=query,
            intent="REFUSED",
            plan_hash=None,
            risk=RiskLevel.BLOCKED,
            decision=AuditDecision.REFUSED,
            errors=[parsed.reason],
        )
        print(f"Refusal: {parsed.reason}", file=sys.stderr)
        return 1

    if isinstance(parsed, Clarification):
        print(f"Clarification Needed: {parsed.question}")
        for i, opt in enumerate(parsed.options, 1):
            print(f"  {i}. {opt}")
        return 0

    try:
        plan = DEFAULT_PLANNER.create_plan(parsed)
    except PermissionError as pe:
        DEFAULT_AUDIT_LOGGER.log(
            session_id="cli",
            original_text=query,
            intent=parsed.operation,
            plan_hash=None,
            risk=RiskLevel.BLOCKED,
            decision=AuditDecision.DENIED,
            errors=[str(pe)],
        )
        print(f"Permission Refused: {pe}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Planning Error: {exc}", file=sys.stderr)
        return 1

    DEFAULT_PLAN_STORE.store_plan(plan)

    if plan.risk_level == RiskLevel.SAFE:
        approved = DEFAULT_PLAN_STORE.approve_plan(plan.plan_id, plan.plan_hash)
        result = DEFAULT_EXECUTOR.execute(approved)
        for outcome in result.outcomes:
            print(outcome.message)
        return 0

    # For MODIFY or DESTRUCTIVE: Show preview and ask for approval in interactive TTY
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("Error: Sensitive action requires interactive TTY approval.", file=sys.stderr)
        return 1

    print("\n=== Plan Preview ===")
    print(f"Operation: {plan.operation}")
    print(f"Risk Level: {plan.risk_level.value}")
    print(f"Summary: {plan.summary}")
    print(f"Consequences: {plan.consequences}")
    print(f"Confirmation Required: {plan.confirmation_hint.prompt_message}")

    typed_input: str | None = None
    if plan.risk_level == RiskLevel.DESTRUCTIVE:
        typed_input = input("Enter confirmation token: ").strip()
    else:
        resp = input("Approve this plan? [y/N]: ").strip().lower()
        if resp != "y":
            print("Operation cancelled.")
            return 1

    try:
        approved = DEFAULT_PLAN_STORE.approve_plan(
            plan.plan_id,
            plan.plan_hash,
            confirmation_input=typed_input,
        )
        result = DEFAULT_EXECUTOR.execute(approved)
        for outcome in result.outcomes:
            print(outcome.message)
        return 0
    except Exception as exc:
        print(f"Execution Error: {exc}", file=sys.stderr)
        return 1


def handle_permissions(args: argparse.Namespace) -> int:
    """Handle `shellsense permissions` subcommands."""
    gate = PermissionGate()
    action = args.permission_action

    if action == "show" or action is None:
        if gate.is_locked():
            print("Status: LOCKED (Zero system capabilities granted)")
            print("Run 'shellsense permissions grant' to configure access.")
            return 0

        grant = gate.get_current_grant()
        if grant is None:
            print("Status: LOCKED")
            return 0

        print("Status: ACTIVE")
        print(f"Platform: {grant.os_platform}")
        print(f"User: {grant.username}")
        print(f"Capabilities ({len(grant.capabilities)}):")
        for cap in grant.capabilities:
            print(f"  - {cap.value}")
        print(f"Folder Roots ({len(grant.folder_roots)}):")
        for root in grant.folder_roots:
            print(f"  - {root}")
        return 0

    if action == "revoke":
        if gate.revoke():
            print("Permissions successfully revoked. ShellSense is now LOCKED.")
        else:
            print("ShellSense was already LOCKED (no active grant found).")
        return 0

    if action == "grant":
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            print(
                "Error: 'permissions grant' requires an interactive human terminal (TTY).",
                file=sys.stderr,
            )
            return 1

        print("=== ShellSense Capability Grant Wizard ===")
        print("This wizard establishes your explicit, local capability grant.")
        print()

        selected_caps: list[Capability] = []
        for cap in Capability:
            resp = input(f"Grant capability {cap.value}? [y/N]: ").strip().lower()
            if resp == "y":
                selected_caps.append(cap)

        roots: list[str] = []
        file_caps = {Capability.FILES_READ, Capability.FILES_MODIFY, Capability.FILES_TRASH}
        if any(c in selected_caps for c in file_caps):
            print("\nEnter folder roots that ShellSense is permitted to access.")
            print("(Do not choose your entire home directory. Choose specific folders).")
            while True:
                path_input = input("Enter allowed folder path (or press Enter to finish): ").strip()
                if not path_input:
                    break
                p = Path(path_input).expanduser().resolve()
                if not p.exists():
                    print(f"Warning: Path '{p}' does not exist on disk.")
                roots.append(str(p))

        if not roots and any(c in selected_caps for c in file_caps):
            print(
                "Error: File capabilities selected but no folder roots were provided. Aborting.",
                file=sys.stderr,
            )
            return 1

        print("\nSummary of Requested Grant:")
        print(f"Capabilities: {[c.value for c in selected_caps]}")
        print(f"Folder Roots: {roots}")
        confirmation = input("Type 'I GRANT ACCESS' to confirm: ").strip()
        if confirmation != "I GRANT ACCESS":
            print("Grant cancelled. No changes written.")
            return 1

        try:
            gate.write_grant(selected_caps, roots, force_tty_check=True)
            print("Grant successfully written. ShellSense capabilities are now active.")
            return 0
        except Exception as e:
            print(f"Failed to record grant: {e}", file=sys.stderr)
            return 1

    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI main entry point."""
    args_list = argv if argv is not None else sys.argv[1:]

    # Invariant 3: Unconditional refusal if running as root or Administrator
    adapter = get_platform_adapter()
    if adapter.is_root_or_admin():
        print(
            "Security Violation: ShellSense refuses to run as root or Administrator.",
            file=sys.stderr,
        )
        return 1

    parser = argparse.ArgumentParser(
        prog="shellsense",
        description="ShellSense: Cross-platform natural-language desktop assistant.",
    )
    subparsers = parser.add_subparsers(dest="command")

    perm_parser = subparsers.add_parser("permissions", help="Inspect and manage capability grants")
    perm_parser.add_argument(
        "permission_action",
        choices=["show", "grant", "revoke"],
        nargs="?",
        default="show",
        help="Action to perform",
    )

    ask_parser = subparsers.add_parser("ask", help="Execute a plain-English request")
    ask_parser.add_argument("query", nargs="+", help="Natural language query string")

    subparsers.add_parser("gui", help="Launch native desktop GUI window")

    args, unknown = parser.parse_known_args(args_list)

    if args.command == "permissions":
        return handle_permissions(args)

    if args.command == "ask":
        query_str = " ".join(args.query)
        return handle_ask(query_str)

    if args.command == "gui":
        frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
        launch_desktop(static_dir=frontend_dist if frontend_dist.exists() else None)
        return 0

    if unknown:
        # Direct string query shortcut: `shellsense "Show my RAM usage"`
        return handle_ask(" ".join(unknown))

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

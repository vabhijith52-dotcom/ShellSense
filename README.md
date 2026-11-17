# ShellSense

**ShellSense** is a cross-platform (Ubuntu 24.04 and Windows 11) natural-language desktop assistant that turns plain-English requests into safe, previewed, and user-approved operating system operations.

---

## The One Rule

> **ShellSense may understand and prepare any operation on its own, but it must never perform a modifying, destructive, or privileged operation without explicit approval from the user, bound to the exact plan that was shown.**

---

## Core Security Invariants

1. **Fail Closed:** Unknown intent, missing risk level, unparseable input, or safety exceptions immediately trigger `REFUSE`. Permissive defaults or `None` risk levels are strictly forbidden.
2. **No Shell Invocations:** Zero usage of `shell=True`, `os.system`, string-interpolated commands, `eval`, or `exec`. Never invoke `cmd.exe`, `powershell`, `wsl`, or `bash`. All operations use direct Python platform APIs (`pathlib`, `shutil`, `psutil`, `os.kill`, `send2trash`).
3. **No Privilege Escalation:** Zero `sudo` or UAC elevation. ShellSense unconditionally refuses to run as root or Administrator.
4. **No Permanent Deletion in v1:** "Delete" strictly means move to the desktop Trash (Linux Freedesktop Trash) / Recycle Bin (Windows) via `send2trash`, backed by an immutable undo record.
5. **Separation of Planning and Execution:** The NLP layer and frontend can only produce an `Intent` or request a `Plan`. They cannot produce commands, cannot name targets in an approval, and cannot invoke the executor.
6. **Immutable ApprovedPlan Binding:** The executor accepts exclusively an `ApprovedPlan`. It re-verifies the SHA-256 plan hash and re-verifies every target immediately prior to acting.
7. **Single-Use Approval Tokens:** Approval is cryptographically bound to the exact plan hash and expires (default 120s). Approvals cannot be reused, replayed, or altered.
8. **Comprehensive Audit Logging:** Every decision (auto-allowed, approved, denied, refused, failed) is recorded in append-only JSONL format, including the verbatim untrusted user input.
9. **Untrusted Input Sanitization:** All text (user inputs, filenames, process metadata, logs) is treated as untrusted. Control characters, ANSI escapes, and Unicode bidirectional override characters (such as RLO) are stripped before display. Text is rendered strictly as text with no `innerHTML` or `dangerouslySetInnerHTML`.
10. **Locked by Default:** Fresh installations possess zero system access until the local human user grants permission via an interactive TTY or the first-run consent wizard.
11. **Local API Hardening:** The backend binds strictly to `127.0.0.1` on a dynamic port, secured by an ephemeral 32-byte session token, strict Host/Origin validation, and rigid CSP headers.
12. **Offline & Zero Telemetry:** Completely offline with zero external network requests, bundled assets, and no telemetry.

---

## Honest Limits

> **Important Security Boundary Statement**
>
> ShellSense is open-source software. Anyone who inspects or modifies the source code could alter or bypass internal safety checks. Therefore:
>
> 1. **Guardrail, Not a Sandbox:** ShellSense's consent and capability system is designed as a robust guardrail against unintended actions, prompt injection, and accidental damage during honest use. It is **not** an operating system security boundary.
> 2. **OS Permissions are the Ultimate Boundary:** ShellSense operates strictly within the privileges of the active local user account. It never attempts or allows privilege escalation (`sudo` or Windows UAC).
> 3. **Recommended Hardening:** For untrusted automation or heightened isolation, ShellSense should be run inside dedicated OS sandboxes:
>    - **Linux:** Run via `bubblewrap` or `firejail`, or under a dedicated unprivileged user account.
>    - **Windows:** Run inside Windows Sandbox or an unprivileged standard user account.

---

## Architecture Overview

```text
shellsense/
├── pyproject.toml                 # Backend dependencies, packaging, ruff & mypy configuration
├── README.md                      # Architecture, safety invariants, honest limits
├── src/shellsense/
│   ├── models.py                  # Frozen Intent, Plan, ApprovedPlan, RiskLevel, Result
│   ├── nlp/                       # Rule-based intent parser and schemas
│   ├── planner.py                 # Resolves targets, computes SHA-256 hash, builds Plan
│   ├── safety/                    # Classifier, policy, path guard, approval store, consent gate
│   ├── platform/                  # OS-specific adapters (Linux & Windows)
│   ├── operations/                # Operation registry, system info, file ops, process ops
│   ├── executor/                  # Executor (sole gate for side-effects) and background jobs
│   ├── storage/                   # JSONL audit log, SQLite history, undo records
│   ├── monitor/                   # Hardware resource ring buffer (CPU, RAM, Disk)
│   ├── api/                       # FastAPI application, security middleware, WebSocket hub
│   ├── gui/                       # Native desktop launcher via pywebview
│   ├── cli.py                     # Headless CLI adapter
│   └── config/                    # Settings models and default configuration
├── frontend/                      # React 18, TypeScript, Vite, Tailwind CSS, Framer Motion
└── tests/                         # Comprehensive backend safety and security test suites
```

---

## Getting Started & Installation

### Prerequisites
- Python 3.12+
- Node.js 20+ & npm 10+

### 1. Clone & Backend Setup
```bash
# Clone the repository
git clone <your-repo-url>
cd shellsense

# Create virtual environment
# On Linux / macOS:
python3 -m venv .venv
source .venv/bin/activate

# On Windows (PowerShell):
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install package and dependencies in editable mode
pip install -e ".[dev]"

# Run verification suite (62 safety, classifier, API, and platform tests)
pytest -v
ruff check src tests
mypy src tests
```

### 2. Frontend Setup & Build
```bash
cd frontend
npm install
npm test
npm run typecheck
npm run build
cd ..
```

---

## Running ShellSense

### 1. Launching the Desktop Application
The desktop app runs a native window using `pywebview` with automatic browser fallback, serving the embedded production frontend over a secured random loopback port:
```bash
# Direct command (when installed in venv)
shellsense

# Or via Python module
python3 -m shellsense

# Or explicitly via CLI sub-command
shellsense gui
```

### 2. Using the Headless CLI Interface
The CLI adapter exposes the identical hardened core, safety pipeline, audit logging, and permission gates without requiring a GUI:
```bash
# Check current system capability grant status
shellsense permissions show

# Interactively grant capabilities (requires interactive human TTY)
shellsense permissions grant

# Revoke all granted capabilities (locks the system)
shellsense permissions revoke

# Ask ShellSense to perform an operation
shellsense ask "Show my RAM usage"
shellsense ask "List files in ~/Downloads"
shellsense ask "Delete old_report.pdf"  # Generates plan and prompts for approval
```

---

## Standalone Packaging (PyInstaller)

To build a zero-dependency standalone binary with the frontend bundled as static assets:
```bash
# 1. Build the frontend production bundle
cd frontend && npm run build && cd ..

# 2. Package with PyInstaller
pyinstaller shellsense.spec

# 3. Executable will be produced in dist/shellsense
./dist/shellsense
```

---

## Verification & Audit Checks

Run the complete verification matrix across backend and frontend:
```bash
# Backend pytest suite (59 safety, model, API, and platform tests)
pytest -v

# Backend linter and static type checker
ruff check src tests
mypy src tests

# Frontend unit tests and TypeScript compiler
cd frontend
npm test
npm run typecheck
```

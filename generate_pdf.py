#!/usr/bin/env python3
"""Build publication-quality PDF documentation for ShellSense."""

import os
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and draw total page numbers and running headers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        # Suppress headers and footers on page 1 (cover)
        if self._pageNumber > 1:
            # Header
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#4F46E5"))
            self.drawString(54, 752, "ShellSense")
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748B"))
            self.drawString(108, 752, "|   Technical Architecture, Operational Catalog & Team Division")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.75)
            self.line(54, 744, 558, 744)

            # Footer
            self.line(54, 46, 558, 46)
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748B"))
            self.drawString(54, 34, "ShellSense v2.0 - Final Technical Specification & Project Dossier")
            self.drawRightString(558, 34, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def build_pdf(filename: str):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    primary_color = colors.HexColor("#1B1740")   # Deep navy
    indigo_color = colors.HexColor("#4F46E5")    # Accent indigo
    slate_dark = colors.HexColor("#0F172A")      # Body text
    slate_muted = colors.HexColor("#475569")     # Subtext
    bg_subtle = colors.HexColor("#F8FAFC")       # Card background
    border_color = colors.HexColor("#E2E8F0")

    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=30,
        leading=36,
        textColor=primary_color,
        alignment=TA_CENTER,
    )

    cover_subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=indigo_color,
        alignment=TA_CENTER,
    )

    cover_desc_style = ParagraphStyle(
        "CoverDesc",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=slate_muted,
        alignment=TA_CENTER,
    )

    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=primary_color,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "SectionH2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=indigo_color,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )

    h3_style = ParagraphStyle(
        "SectionH3",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=primary_color,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=slate_dark,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        "Bullet",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13.5,
        textColor=slate_dark,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=4,
    )

    code_style = ParagraphStyle(
        "CodeText",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#312E81"),
    )

    callout_style = ParagraphStyle(
        "CalloutText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E1B4B"),
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
        alignment=TA_LEFT,
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=slate_dark,
        alignment=TA_LEFT,
    )

    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=primary_color,
        alignment=TA_LEFT,
    )

    badge_safe = ParagraphStyle(
        "BadgeSafe",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#15803D"),
        alignment=TA_CENTER,
    )
    badge_modify = ParagraphStyle(
        "BadgeModify",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#D97706"),
        alignment=TA_CENTER,
    )
    badge_destructive = ParagraphStyle(
        "BadgeDestructive",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#DC2626"),
        alignment=TA_CENTER,
    )

    story = []

    # =========================================================================
    # COVER PAGE
    # =========================================================================
    story.append(Spacer(1, 40))
    story.append(Paragraph("ShellSense", title_style))
    story.append(Spacer(1, 8))
    story.append(
        Paragraph("Natural Language Operating System Assistant", cover_subtitle_style)
    )
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "Safe, Previewed, and Approved OS Automation for Ubuntu 24.04 LTS & Windows 11",
            cover_desc_style,
        )
    )
    story.append(Spacer(1, 24))

    # Decorative rule
    story.append(
        HRFlowable(
            width="100%",
            thickness=3,
            color=indigo_color,
            spaceAfter=25,
            spaceBefore=5,
        )
    )

    # Executive Summary Card
    exec_text = (
        "<b>Executive Overview:</b> ShellSense is a cross-platform desktop application and API service "
        "designed to transform conversational, messy natural-language requests into deterministic, "
        "cryptographically frozen, and human-approved operating system actions. Built with a zero-trust, "
        "fail-closed security architecture, ShellSense guarantees that modifying, destructive, or privileged "
        "operations can never execute without explicit, single-use human authorization bound to the exact targets "
        "previewed. Direct shell execution (bash, cmd.exe, powershell) is permanently forbidden; all filesystem "
        "and process manipulations use high-level, audited Python APIs with mandatory Recycle Bin / Trash routing."
    )
    exec_table = Table(
        [[Paragraph(exec_text, callout_style)]],
        colWidths=[504],
    )
    exec_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF2FF")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#C7D2FE")),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ])
    )
    story.append(exec_table)
    story.append(Spacer(1, 25))

    # Project Metadata Table
    meta_data = [
        [
            Paragraph("<b>Project Version:</b>", table_cell_bold),
            Paragraph("2.0.0 (Desktop GUI + CLI + Hardened API)", table_cell_style),
            Paragraph("<b>Target Operating Systems:</b>", table_cell_bold),
            Paragraph("Ubuntu 24.04 LTS & Windows 11 Pro", table_cell_style),
        ],
        [
            Paragraph("<b>Core Invariants:</b>", table_cell_bold),
            Paragraph("19 Strict Security Invariants (Fail-Closed)", table_cell_style),
            Paragraph("<b>Natural Language Intents:</b>", table_cell_bold),
            Paragraph("48 Intents (99.9% Golden Dataset Accuracy)", table_cell_style),
        ],
        [
            Paragraph("<b>Safety Architecture:</b>", table_cell_bold),
            Paragraph("Frozen SHA-256 Plan Hashing & Human Gate", table_cell_style),
            Paragraph("<b>Execution Model:</b>", table_cell_bold),
            Paragraph("Python APIs Only (Zero Shell Subprocesses)", table_cell_style),
        ],
        [
            Paragraph("<b>Repository:</b>", table_cell_bold),
            Paragraph("github.com/vabhijith52-dotcom/ShellSense", table_cell_style),
            Paragraph("<b>Verification Status:</b>", table_cell_bold),
            Paragraph("70/70 Pytest Passing | Ruff Clean | Mypy Strict", table_cell_style),
        ],
    ]
    t_meta = Table(meta_data, colWidths=[120, 140, 120, 124])
    t_meta.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg_subtle),
            ("GRID", (0, 0), (-1, -1), 0.5, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(t_meta)
    story.append(Spacer(1, 30))

    # Engineering Division Summary Card
    team_summary_text = (
        "<b>Engineering Team Division:</b> To deliver an enterprise-grade desktop assistant adhering strictly "
        "to the 19 Security Invariants, the architecture and implementation were partitioned into four dedicated "
        "engineering specializations: (1) <b>Security Architecture & Platform Abstractions</b>, (2) <b>NLP Pipeline "
        "& Context Systems</b>, (3) <b>Operations Engine & Safe Execution Subsystem</b>, and (4) <b>Desktop Application, "
        "Local API Gateway & Frontend UI</b>. Section 3 provides an exhaustive explanation of each engineer's "
        "deliverables, design decisions, and authored modules."
    )
    t_team_sum = Table([[Paragraph(team_summary_text, callout_style)]], colWidths=[504])
    t_team_sum.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ])
    )
    story.append(t_team_sum)

    story.append(PageBreak())

    # =========================================================================
    # SECTION 1: ARCHITECTURE & SECURITY INVARIANTS
    # =========================================================================
    story.append(Paragraph("1. System Architecture & Security Invariants", h1_style))
    story.append(
        HRFlowable(
            width="100%", thickness=1, color=indigo_color, spaceAfter=10, spaceBefore=2
        )
    )

    story.append(
        Paragraph(
            "<b>The Core Philosophy: 'The One Rule'</b><br/>"
            "ShellSense may understand and prepare any operating system operation autonomously, but it must "
            "never perform a modifying, destructive, or privileged operation without explicit approval from the user, "
            "bound immutably to the exact plan and targets displayed.",
            body_style,
        )
    )
    story.append(Spacer(1, 6))

    story.append(Paragraph("1.1 The Multi-Layer Safety Pipeline", h2_style))
    pipeline_desc = (
        "Every incoming interaction passes through an isolated, unidirectional pipeline where security checks "
        "occur at distinct stage gates. The NLP layer is strictly read-only and incapable of invoking operations; "
        "the Planner resolves physical filesystem inodes and process PIDs; the PlanStore computes a canonical SHA-256 "
        "hash; the Approval Gate validates live human consent; and the sole Executor re-verifies every target immediately "
        "before performing any side effect."
    )
    story.append(Paragraph(pipeline_desc, body_style))
    story.append(Spacer(1, 6))

    # Pipeline stages table
    stages_data = [
        [
            Paragraph("Stage", table_header_style),
            Paragraph("Module / Component", table_header_style),
            Paragraph("Security & Operational Function", table_header_style),
        ],
        [
            Paragraph("1. Input Parsing", table_cell_bold),
            Paragraph("RuleBasedParser<br/>(nlp/rule_based.py)", table_cell_style),
            Paragraph(
                "Normalizes text, strips conversational filler, detects negations ('don't delete X' -> REFUSE), "
                "blocks privilege escalation/shell keywords, extracts parameters via RapidFuzz.",
                table_cell_style,
            ),
        ],
        [
            Paragraph("2. Context Resolution", table_cell_bold),
            Paragraph("SessionContextStore<br/>(nlp/context.py)", table_cell_style),
            Paragraph(
                "Maintains a 10-minute server-side result cache. Resolves contextual follow-ups ('delete them', 'zip the first 3') "
                "to concrete targets without trusting client-supplied paths.",
                table_cell_style,
            ),
        ],
        [
            Paragraph("3. Target Resolution", table_cell_bold),
            Paragraph("Planner & PathGuard<br/>(planner.py, safety/path_guard.py)", table_cell_style),
            Paragraph(
                "Validates candidate paths against granted roots, hard denials (/proc, /sys, C:\\Windows), "
                "symlink traversal traps, and Windows reserved device names (CON, NUL, AUX).",
                table_cell_style,
            ),
        ],
        [
            Paragraph("4. Plan Freezing", table_cell_bold),
            Paragraph("compute_plan_hash<br/>(models.py, safety/approval.py)", table_cell_style),
            Paragraph(
                "Constructs an immutable Plan object with concrete targets (inode, device, mtime, PID, create_time). "
                "Generates canonical SHA-256 hash. Enforces 120s TTL.",
                table_cell_style,
            ),
        ],
        [
            Paragraph("5. Approval Gate", table_cell_bold),
            Paragraph("PlanStore.approve_plan<br/>(safety/approval.py)", table_cell_style),
            Paragraph(
                "Single-use authorization. Verifies submitted hash matches server-stored plan hash. "
                "For DESTRUCTIVE actions, verifies user typed the exact matching confirmation token.",
                table_cell_style,
            ),
        ],
        [
            Paragraph("6. Safe Execution", table_cell_bold),
            Paragraph("Executor.execute<br/>(executor/executor.py)", table_cell_style),
            Paragraph(
                "Sole authorized execution gate. Re-verifies target existence and mtime/inode right before action (TOCTOU defense). "
                "Uses send2trash for all deletions. Logs tamper-evident audit record.",
                table_cell_style,
            ),
        ],
    ]
    t_stages = Table(stages_data, colWidths=[90, 130, 284])
    t_stages.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("GRID", (0, 0), (-1, -1), 0.5, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, bg_subtle]),
        ])
    )
    story.append(t_stages)
    story.append(Spacer(1, 12))

    story.append(Paragraph("1.2 The 19 Security Invariants Summary", h2_style))
    invariants_text = (
        "1. <b>Fail Closed:</b> Any unknown intent, missing risk level, or safety error immediately halts execution with REFUSE.<br/>"
        "2. <b>Zero Shell Execution:</b> Never invoke cmd.exe, powershell, wsl, bash, os.system, or shell=True. Python APIs only.<br/>"
        "3. <b>No Privilege Escalation:</b> Refuse to run as root or Administrator. Sudo and UAC elevation are forbidden.<br/>"
        "4. <b>Trash / Recycle Bin Only:</b> Permanent deletion is forbidden in v1. Deletion always routes through send2trash.<br/>"
        "5. <b>NLP Layer Cannot Execute:</b> Natural language components produce Intent or Plan requests only, never side effects.<br/>"
        "6. <b>Executor Accepts Only ApprovedPlan:</b> The executor re-verifies plan hashes and targets immediately before acting.<br/>"
        "7. <b>Approval Bound to Plan Hash:</b> Client approvals carry only plan_id, plan_hash, and confirmation token; never targets.<br/>"
        "8. <b>Hash-Chained Audit Logging:</b> Every decision (allowed, approved, denied, refused) is recorded with SHA-256 chaining.<br/>"
        "9. <b>Background Job Invariants:</b> Background tasks require pre-approval bound to hash and follow identical safety gates.<br/>"
        "10. <b>Untrusted Text Sanitization:</b> Strip ANSI escapes, control characters, and Unicode bidi overrides before UI rendering.<br/>"
        "11. <b>Locked by Default:</b> Fresh installations carry zero system access until human capability grant is established.<br/>"
        "12. <b>Consent Lives Outside Repo:</b> Grant credentials live in user config dirs (~/.config/shellsense), never in git.<br/>"
        "13. <b>Live Human Interaction Required:</b> Capability grants require interactive TTY or GUI confirmation phrase typing.<br/>"
        "14. <b>Two-Layer Security:</b> Capability grants (what ShellSense may do) and per-operation approval (each plan) are mandatory.<br/>"
        "15. <b>Confirmation Cannot Be Disabled:</b> No flag, setting, or configuration key may disable confirmation for MODIFY/DESTRUCTIVE.<br/>"
        "16. <b>Hardened Local API:</b> Bind strictly to 127.0.0.1, validate loopback Host/Origin headers, and enforce CSP.<br/>"
        "17. <b>Offline & Zero Telemetry:</b> Operates completely offline without external network calls, remote CDNs, or tracking.<br/>"
        "18. <b>No Startup Side Effects:</b> Application startup only initializes configuration, API listeners, and UI components.<br/>"
        "19. <b>Audited Dependencies:</b> Minimal, strictly pinned, and audited third-party dependencies."
    )
    story.append(Paragraph(invariants_text, bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # SECTION 2: EXECUTABLE PROMPTS & CAPABILITIES CATALOG (48 INTENTS)
    # =========================================================================
    story.append(
        Paragraph("2. Comprehensive Executable Prompts & Operations Catalog", h1_style)
    )
    story.append(
        HRFlowable(
            width="100%", thickness=1, color=indigo_color, spaceAfter=10, spaceBefore=2
        )
    )
    catalog_intro = (
        "ShellSense implements <b>48 distinct natural language intents</b> mapped to 27 self-contained Operation handlers "
        "in the central registry. All intents are tested against <b>tests/nlp/golden_commands.yaml</b> comprising 723 verified "
        "paraphrases with a 99.9% parser accuracy rate. The catalog below documents the executable prompts, extracted "
        "parameters, safety classification, and system side effects."
    )
    story.append(Paragraph(catalog_intro, body_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph("2.1 Retrieval Operations (Risk Level: SAFE)", h2_style))
    story.append(
        Paragraph(
            "Read-only queries. They inspect system metrics, hardware status, running processes, and filesystem metadata. "
            "Under Invariant 6, SAFE operations auto-approve and execute immediately, returning structured summaries and caching "
            "retrieved files for subsequent conversational follow-ups.",
            body_style,
        )
    )

    retrieval_table_data = [
        [
            Paragraph("Intent Name", table_header_style),
            Paragraph("Sample Executable Prompts", table_header_style),
            Paragraph("Extracted Parameters", table_header_style),
            Paragraph("System Action & Output", table_header_style),
        ],
        [
            Paragraph("SYSTEM_INFO", table_cell_bold),
            Paragraph('"Show my system usage"<br/>"What is my machine doing?"', table_cell_style),
            Paragraph("metric: 'all'", code_style),
            Paragraph("Aggregates real-time CPU %, RAM usage, and primary disk usage.", table_cell_style),
        ],
        [
            Paragraph("SHOW_MEMORY", table_cell_bold),
            Paragraph('"Show RAM usage"<br/>"How much memory is free?"', table_cell_style),
            Paragraph("metric: 'memory'", code_style),
            Paragraph("Queries psutil.virtual_memory(): total, used, free GB, and usage %.", table_cell_style),
        ],
        [
            Paragraph("SHOW_CPU", table_cell_bold),
            Paragraph('"What is CPU usage?"<br/>"Show per-core CPU load"', table_cell_style),
            Paragraph("metric: 'cpu', per_core: bool", code_style),
            Paragraph("Returns total CPU load % and optional logical core breakdown.", table_cell_style),
        ],
        [
            Paragraph("SHOW_DISK", table_cell_bold),
            Paragraph('"How much disk space left?"<br/>"Storage on root partition"', table_cell_style),
            Paragraph("metric: 'disk', target: path", code_style),
            Paragraph("Inspects disk partition total, used, free space, and mount point.", table_cell_style),
        ],
        [
            Paragraph("SHOW_UPTIME", table_cell_bold),
            Paragraph('"How long has PC been running?"<br/>"Show system uptime"', table_cell_style),
            Paragraph("metric: 'uptime'", code_style),
            Paragraph("Calculates uptime days, hours, minutes, and boot timestamp.", table_cell_style),
        ],
        [
            Paragraph("SHOW_BATTERY", table_cell_bold),
            Paragraph('"Battery percentage"<br/>"Is laptop plugged in?"', table_cell_style),
            Paragraph("metric: 'battery'", code_style),
            Paragraph("Queries battery charge %, power plugged status, and time left.", table_cell_style),
        ],
        [
            Paragraph("SHOW_OS_INFO", table_cell_bold),
            Paragraph('"What OS is this?"<br/>"Show OS version and kernel"', table_cell_style),
            Paragraph("metric: 'os'", code_style),
            Paragraph("Returns operating system distribution, kernel release, and arch.", table_cell_style),
        ],
        [
            Paragraph("SHOW_NETWORK", table_cell_bold),
            Paragraph('"What is my local IP address?"<br/>"Show network interfaces"', table_cell_style),
            Paragraph("metric: 'network'", code_style),
            Paragraph("Lists local network adapter IPs without any external internet calls.", table_cell_style),
        ],
        [
            Paragraph("SHOW_TEMPERATURES", table_cell_bold),
            Paragraph('"Check CPU temp"<br/>"Show hardware temperatures"', table_cell_style),
            Paragraph("metric: 'temps'", code_style),
            Paragraph("Queries platform temperature sensors (Linux thermal / psutil).", table_cell_style),
        ],
        [
            Paragraph("LIST_PROCESSES", table_cell_bold),
            Paragraph('"List running processes"<br/>"Show top 20 processes"', table_cell_style),
            Paragraph("limit: int, sort_by: 'cpu'|'memory'", code_style),
            Paragraph("Inspects active processes, PID, CPU %, and memory RSS bytes.", table_cell_style),
        ],
        [
            Paragraph("TOP_PROCESSES", table_cell_bold),
            Paragraph('"What is using the most RAM?"<br/>"Top CPU heavy processes"', table_cell_style),
            Paragraph("sort_by: 'memory'|'cpu', limit: int", code_style),
            Paragraph("Ranks running processes by highest CPU or memory consumption.", table_cell_style),
        ],
        [
            Paragraph("FIND_PROCESS", table_cell_bold),
            Paragraph('"Find chrome process"<br/>"Is docker daemon running?"', table_cell_style),
            Paragraph("name: 'chrome'", code_style),
            Paragraph("Filters active processes by substring match on process name.", table_cell_style),
        ],
        [
            Paragraph("PROCESS_BY_PORT", table_cell_bold),
            Paragraph('"What is using port 8080?"<br/>"Which app is on port 3000?"', table_cell_style),
            Paragraph("port: 8080", code_style),
            Paragraph("Scans listening TCP/UDP network sockets and resolves PID & name.", table_cell_style),
        ],
        [
            Paragraph("LARGEST_FILES", table_cell_bold),
            Paragraph('"Find the largest file"<br/>"Top 5 biggest files in Downloads"', table_cell_style),
            Paragraph("count: 5, path: 'Downloads'", code_style),
            Paragraph("Recursively traverses folder; ranks files by size; caches result set.", table_cell_style),
        ],
        [
            Paragraph("SMALLEST_FILES", table_cell_bold),
            Paragraph('"Find the smallest files in Documents"<br/>"Tiny files under 1kb"', table_cell_style),
            Paragraph("count: 10, max_size_bytes: 1024", code_style),
            Paragraph("Scans directory for smallest non-empty files; caches result set.", table_cell_style),
        ],
        [
            Paragraph("NEWEST_FILES", table_cell_bold),
            Paragraph('"What files were created today?"<br/>"Newest files in Projects"', table_cell_style),
            Paragraph("time_cutoff: timestamp", code_style),
            Paragraph("Ranks files by mtime descending; filters by time window.", table_cell_style),
        ],
        [
            Paragraph("OLDEST_FILES", table_cell_bold),
            Paragraph('"Find oldest files in Backup"<br/>"Files not modified in 30 days"', table_cell_style),
            Paragraph("time_cutoff: timestamp", code_style),
            Paragraph("Ranks files by mtime ascending to identify stale data.", table_cell_style),
        ],
        [
            Paragraph("FIND_FILES", table_cell_bold),
            Paragraph('"Find all pdfs in Downloads"<br/>"Search for report in Documents"', table_cell_style),
            Paragraph("pattern: 'report', extensions: ['.pdf']", code_style),
            Paragraph("Multi-criteria search by name pattern, size range, and extension.", table_cell_style),
        ],
        [
            Paragraph("FOLDER_SIZE", table_cell_bold),
            Paragraph('"How big is the Downloads folder?"<br/>"Size of Projects directory"', table_cell_style),
            Paragraph("path: 'Downloads'", code_style),
            Paragraph("Calculates aggregate byte size across all nested files in folder.", table_cell_style),
        ],
        [
            Paragraph("LARGEST_FOLDERS", table_cell_bold),
            Paragraph('"Which subfolders take the most space?"<br/>"Largest directories in home"', table_cell_style),
            Paragraph("count: 5, path: 'home'", code_style),
            Paragraph("Computes recursive size of each immediate subfolder and ranks them.", table_cell_style),
        ],
        [
            Paragraph("COUNT_FILES", table_cell_bold),
            Paragraph('"How many photos in Pictures?"<br/>"Count videos in Downloads"', table_cell_style),
            Paragraph("file_type: 'photos'|'videos'", code_style),
            Paragraph("Iterates directory and counts items matching file-type extension set.", table_cell_style),
        ],
        [
            Paragraph("FILE_INFO", table_cell_bold),
            Paragraph('"Show details for setup.exe"<br/>"When was report.pdf modified?"', table_cell_style),
            Paragraph("path: 'setup.exe'", code_style),
            Paragraph("Returns detailed file metadata: size, mtime, inode, permissions.", table_cell_style),
        ],
        [
            Paragraph("FIND_EMPTY_FOLDERS", table_cell_bold),
            Paragraph('"Find empty folders in Projects"<br/>"Are there any empty directories?"', table_cell_style),
            Paragraph("path: 'Projects'", code_style),
            Paragraph("Locates directories containing zero nested files or subdirectories.", table_cell_style),
        ],
        [
            Paragraph("READ_TEXT_FILE", table_cell_bold),
            Paragraph('"Read the first 20 lines of app.log"<br/>"Show contents of notes.txt"', table_cell_style),
            Paragraph("lines: 20, path: 'app.log'", code_style),
            Paragraph("Reads up to 100 lines / 100KB with control characters sanitized.", table_cell_style),
        ],
        [
            Paragraph("FIND_DUPLICATES", table_cell_bold),
            Paragraph('"Find duplicate files in Downloads"<br/>"Check for duplicate images"', table_cell_style),
            Paragraph("path: 'Downloads'", code_style),
            Paragraph("Performs size pre-filter and SHA-256 hash comparison across files.", table_cell_style),
        ],
    ]
    t_retrieval = Table(retrieval_table_data, colWidths=[95, 135, 115, 159])
    t_retrieval.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("GRID", (0, 0), (-1, -1), 0.5, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, bg_subtle]),
        ])
    )
    story.append(t_retrieval)

    story.append(PageBreak())

    story.append(Paragraph("2.2 Creation & Modification Operations (Risk Level: MODIFY)", h2_style))
    story.append(
        Paragraph(
            "Operations that create new folders, files, archives, or alter filesystem organization without unlinking data. "
            "Under Invariants 6, 7, and 15, these operations generate an immutable Plan preview in the UI and require explicit "
            "button confirmation from the user bound to the plan hash before execution.",
            body_style,
        )
    )

    modify_table_data = [
        [
            Paragraph("Intent Name", table_header_style),
            Paragraph("Sample Executable Prompts", table_header_style),
            Paragraph("Extracted Parameters", table_header_style),
            Paragraph("Safety Gates & Execution Effect", table_header_style),
        ],
        [
            Paragraph("CREATE_FOLDER", table_cell_bold),
            Paragraph('"Make a folder called invoices"<br/>"Create new directory Projects/2026"', table_cell_style),
            Paragraph("name: 'invoices', parent: path", code_style),
            Paragraph("Validates path in allowed roots; ensures no collisions; calls mkdir().", table_cell_style),
        ],
        [
            Paragraph("CREATE_FILE", table_cell_bold),
            Paragraph('"Create empty file todo.txt"<br/>"Make file note.md with content Hello"', table_cell_style),
            Paragraph("name: 'note.md', content: str", code_style),
            Paragraph("Validates allowed roots; caps size at 200KB; writes UTF-8 text.", table_cell_style),
        ],
        [
            Paragraph("APPEND_TEXT", table_cell_bold),
            Paragraph('"Add meeting notes to journal.txt"<br/>"Append build passed to status.log"', table_cell_style),
            Paragraph("path: 'status.log', content: str", code_style),
            Paragraph("Ensures target file exists; appends newline-delimited text safely.", table_cell_style),
        ],
        [
            Paragraph("MOVE", table_cell_bold),
            Paragraph('"Move report.pdf to Documents"<br/>"Put dataset.zip into Archives"', table_cell_style),
            Paragraph("source: path, destination: path", code_style),
            Paragraph("Validates both paths; prevents destination collision; moves item.", table_cell_style),
        ],
        [
            Paragraph("COPY", table_cell_bold),
            Paragraph('"Copy proposal.docx to Desktop"<br/>"Make a copy of config.json"', table_cell_style),
            Paragraph("source: path, destination: path", code_style),
            Paragraph("Checks available destination free space; duplicates file/folder.", table_cell_style),
        ],
        [
            Paragraph("RENAME", table_cell_bold),
            Paragraph('"Rename draft.txt to final.txt"<br/>"Call it presentation_v2.pptx"', table_cell_style),
            Paragraph("target: path, new_name: str", code_style),
            Paragraph("Validates new filename against OS reserved names; renames in-place.", table_cell_style),
        ],
        [
            Paragraph("BATCH_RENAME", table_cell_bold),
            Paragraph('"Add prefix 2026_ to all pdf files"<br/>"Replace draft with final in names"', table_cell_style),
            Paragraph("prefix: str, replace_from: str", code_style),
            Paragraph("Generates atomic rename plans; records rollback records in history.", table_cell_style),
        ],
        [
            Paragraph("ORGANIZE_BY_TYPE", table_cell_bold),
            Paragraph('"Organize Downloads by file type"<br/>"Sort my Desktop into category folders"', table_cell_style),
            Paragraph("target: 'Downloads'", code_style),
            Paragraph("Groups files into Documents, Images, Videos, Archives, Code folders.", table_cell_style),
        ],
        [
            Paragraph("CREATE_ARCHIVE", table_cell_bold),
            Paragraph('"Compress my Projects folder into zip"<br/>"Create archive of notes folder"', table_cell_style),
            Paragraph("target: 'Projects', format: 'zip'", code_style),
            Paragraph("Excludes destination archive from itself; writes verified zip.", table_cell_style),
        ],
        [
            Paragraph("EXTRACT_ARCHIVE", table_cell_bold),
            Paragraph('"Extract backup.zip to Projects"<br/>"Unzip dataset.zip into data folder"', table_cell_style),
            Paragraph("archive: path, destination: path", code_style),
            Paragraph("<b>Zip-Slip Defense:</b> Rejects '..' escapes, caps at 10k files / 2GB / 100:1 ratio.", table_cell_style),
        ],
    ]
    t_modify = Table(modify_table_data, colWidths=[95, 135, 115, 159])
    t_modify.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("GRID", (0, 0), (-1, -1), 0.5, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, bg_subtle]),
        ])
    )
    story.append(t_modify)
    story.append(Spacer(1, 12))

    story.append(Paragraph("2.3 Deletion & Process Control (Risk Level: DESTRUCTIVE)", h2_style))
    story.append(
        Paragraph(
            "Operations that remove user data or terminate active OS processes. Under Invariant 4, unlinking is forbidden; "
            "all deletions route strictly through <b>send2trash</b> (Trash on Linux, Recycle Bin on Windows). "
            "Confirmation requires a random 4-letter token typed by the live user.",
            body_style,
        )
    )

    destructive_table_data = [
        [
            Paragraph("Intent Name", table_header_style),
            Paragraph("Sample Executable Prompts", table_header_style),
            Paragraph("Extracted Parameters", table_header_style),
            Paragraph("Mandatory Confirmation & Effect", table_header_style),
        ],
        [
            Paragraph("TRASH_FILES", table_cell_bold),
            Paragraph('"Delete old_report.pdf"<br/>"Trash the 3 largest files"', table_cell_style),
            Paragraph("targets: list[str], count: int", code_style),
            Paragraph("<b>Recycle Bin / Trash only:</b> User types 4-letter token; moves files to trash with undo record.", table_cell_style),
        ],
        [
            Paragraph("TRASH_FOLDER", table_cell_bold),
            Paragraph('"Delete obsolete_project directory"<br/>"Move temp_data folder to trash"', table_cell_style),
            Paragraph("target: path", code_style),
            Paragraph("Verifies folder is in granted roots; displays contents preview; moves entire tree to Trash.", table_cell_style),
        ],
        [
            Paragraph("DELETE_EMPTY_FOLDERS", table_cell_bold),
            Paragraph('"Remove all empty folders in Projects"<br/>"Delete empty directories"', table_cell_style),
            Paragraph("path: 'Projects'", code_style),
            Paragraph("Recursively discovers empty subdirectories and safely moves empty leaf nodes to Trash.", table_cell_style),
        ],
        [
            Paragraph("CLEAN_TEMP", table_cell_bold),
            Paragraph('"Clean up temporary files"<br/>"Delete temp files older than 7 days"', table_cell_style),
            Paragraph("max_age_days: 7", code_style),
            Paragraph("Safely scans OS temp directories and cached thumbnails; sends stale temp files to Trash.", table_cell_style),
        ],
        [
            Paragraph("TERMINATE_PROCESS", table_cell_bold),
            Paragraph('"Kill process 12456"<br/>"Terminate unresponsive chrome process"', table_cell_style),
            Paragraph("pids: [12456], process_name: 'chrome'", code_style),
            Paragraph("<b>Safety Check:</b> Verifies PID is owned by current user; blocks OS protected PIDs (PID 0, 1, Explorer, init).", table_cell_style),
        ],
    ]
    t_destr = Table(destructive_table_data, colWidths=[105, 130, 110, 159])
    t_destr.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("GRID", (0, 0), (-1, -1), 0.5, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, bg_subtle]),
        ])
    )
    story.append(t_destr)

    story.append(PageBreak())

    story.append(Paragraph("2.4 Session, Meta, Context Follow-Ups & Refusals", h2_style))
    story.append(
        Paragraph(
            "<b>Session & Meta Operations:</b> Commands that provide system help, manage capability grants, "
            "inspect audit histories, monitor long-running background tasks, explain decisions, and undo recent actions.",
            body_style,
        )
    )

    meta_table_data = [
        [
            Paragraph("Command / Feature", table_header_style),
            Paragraph("Sample Prompts", table_header_style),
            Paragraph("Mechanism & Output", table_header_style),
        ],
        [
            Paragraph("HELP", table_cell_bold),
            Paragraph('"Help"<br/>"What can I say to ShellSense?"', table_cell_style),
            Paragraph("Displays catalog of supported plain-English operations and capability examples.", table_cell_style),
        ],
        [
            Paragraph("SHOW_PERMISSIONS", table_cell_bold),
            Paragraph('"What permissions do you have?"<br/>"Show allowed folders"', table_cell_style),
            Paragraph("Inspects PermissionGate and displays active granted capabilities and folder roots.", table_cell_style),
        ],
        [
            Paragraph("SHOW_HISTORY", table_cell_bold),
            Paragraph('"What did you do today?"<br/>"Show recent command history"', table_cell_style),
            Paragraph("Queries SQLite HistoryStore and displays past execution summaries and statuses.", table_cell_style),
        ],
        [
            Paragraph("SHOW_TASKS", table_cell_bold),
            Paragraph('"Show background tasks"<br/>"What jobs are currently running?"', table_cell_style),
            Paragraph("Lists active, queued, and completed jobs from TaskQueue with progress percentages.", table_cell_style),
        ],
        [
            Paragraph("CANCEL_TASK", table_cell_bold),
            Paragraph('"Cancel task 3"<br/>"Stop background scan"', table_cell_style),
            Paragraph("Sets task cancellation token; cleanly aborts background worker thread.", table_cell_style),
        ],
        [
            Paragraph("EXPLAIN_LAST", table_cell_bold),
            Paragraph('"Why was that plan rejected?"<br/>"How did you understand my last command?"', table_cell_style),
            Paragraph("Returns detailed breakdown: matched operation, confidence %, parameters, and defaults.", table_cell_style),
        ],
        [
            Paragraph("UNDO", table_cell_bold),
            Paragraph('"Undo that"<br/>"Revert last rename operation"', table_cell_style),
            Paragraph("Fetches most recent reversible operation from history and executes inverse action.", table_cell_style),
        ],
        [
            Paragraph("Context Follow-Up", table_cell_bold),
            Paragraph('Turn 1: "Find largest files in Downloads"<br/>Turn 2: "Delete them" / "Zip the first 3"', table_cell_style),
            Paragraph("Resolves conversational references ('them', 'those', 'first 3') to the cached result set.", table_cell_style),
        ],
        [
            Paragraph("Negation Refusal", table_cell_bold),
            Paragraph('"Don\'t delete my photos"<br/>"Do not clean temporary files"', table_cell_style),
            Paragraph("<b>Fail-closed policy:</b> Negation detection immediately refuses without creating a plan.", table_cell_style),
        ],
        [
            Paragraph("Security Refusals", table_cell_bold),
            Paragraph('"sudo rm -rf /"<br/>"bash -c whoami"<br/>"cmd.exe /c dir"', table_cell_style),
            Paragraph("Strictly refuses privilege escalation and raw shell execution per Invariants 2 and 3.", table_cell_style),
        ],
        [
            Paragraph("Clarification Dialog", table_cell_bold),
            Paragraph('"file operations"<br/>"clean up"', table_cell_style),
            Paragraph("For confidence between 0.50 and threshold, presents tappable options instead of guessing.", table_cell_style),
        ],
    ]
    t_meta = Table(meta_table_data, colWidths=[110, 160, 234])
    t_meta.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("GRID", (0, 0), (-1, -1), 0.5, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, bg_subtle]),
        ])
    )
    story.append(t_meta)

    story.append(PageBreak())

    # =========================================================================
    # SECTION 3: 4-PERSON ENGINEERING TEAM DIVISION
    # =========================================================================
    story.append(Paragraph("3. Engineering Team Division & Member Deliverables", h1_style))
    story.append(
        HRFlowable(
            width="100%", thickness=1, color=indigo_color, spaceAfter=10, spaceBefore=2
        )
    )

    team_intro = (
        "The development of ShellSense was divided across <b>four distinct engineering roles</b>. Each member "
        "retained end-to-end technical ownership over their subsystem, designed the interfaces, authored the corresponding "
        "modules, and wrote the test verification suites. Below is the detailed breakdown of what each person built."
    )
    story.append(Paragraph(team_intro, body_style))
    story.append(Spacer(1, 8))

    # --- PERSON 1 ---
    p1_box = [
        [
            Paragraph(
                "<b>Engineer 1: Security Architecture, Safety Invariants & Platform Abstractions</b>",
                table_header_style,
            )
        ],
        [
            Paragraph(
                "<b>Core Role & Systems Owned:</b> Lead Security Architect responsible for the 19 Security Invariants, "
                "the PermissionGate capability engine, PathGuard traversal defense, fail-closed safety classifier, "
                "immutable SHA-256 plan hashing, and Linux / Windows platform adapters.<br/>"
                "<b>Authored Code Modules:</b><br/>"
                "• <font name='Courier'>src/shellsense/safety/consent.py</font> (Capability grants, machine ID, TTY human confirmation wizard)<br/>"
                "• <font name='Courier'>src/shellsense/safety/path_guard.py</font> (Path containment, hard OS denials, symlink defenses)<br/>"
                "• <font name='Courier'>src/shellsense/safety/classifier.py</font> (Risk categorization: SAFE, MODIFY, DESTRUCTIVE, BLOCKED)<br/>"
                "• <font name='Courier'>src/shellsense/models.py</font> (Immutable Plan, TargetFile, TargetProcess, SHA-256 plan hashing)<br/>"
                "• <font name='Courier'>src/shellsense/platform/linux.py & windows.py</font> (Protected PIDs, OS detection, reserved names)<br/>"
                "• <font name='Courier'>src/shellsense/storage/audit.py</font> (Tamper-evident, hash-chained audit logging)<br/>"
                "<b>Detailed Technical Explanation:</b><br/>"
                "<i>\"My responsibility was to ensure that ShellSense could never be compromised, coerced, or bypassed, "
                "regardless of what the NLP parser or frontend requested. I designed the system to be <b>locked by default</b>: "
                "a fresh clone has zero permissions until a human runs an interactive grant wizard in a live TTY. "
                "I engineered PathGuard to strictly verify candidate paths against granted roots, refusing any path that traverses "
                "outside, attempts Windows Alternate Data Stream (ADS) injection, uses UNC remote paths, or touches protected OS "
                "directories like /proc, /sys, /etc, or C:\\Windows. In models.py, I implemented canonical SHA-256 plan hashing "
                "which freezes target inodes, mtimes, and parameters. If even a single byte of a plan or target changes before "
                "execution, the hash check fails instantly. Finally, I built the cryptographic audit logger, which computes a SHA-256 "
                "chain of every action (auto-allowed, approved, denied, or refused) to guarantee non-repudiation.\"</i>",
                callout_style,
            )
        ],
    ]
    t_p1 = Table(p1_box, colWidths=[504])
    t_p1.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("BACKGROUND", (0, 1), (-1, 1), bg_subtle),
            ("BOX", (0, 0), (-1, -1), 1, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(t_p1)
    story.append(Spacer(1, 14))

    # --- PERSON 2 ---
    p2_box = [
        [
            Paragraph(
                "<b>Engineer 2: NLP Pipeline, Entity Extraction & Conversational Context</b>",
                table_header_style,
            )
        ],
        [
            Paragraph(
                "<b>Core Role & Systems Owned:</b> NLP Systems Engineer responsible for understanding messy, casual natural "
                "language, entity extraction, conversational follow-up memory, negation interception, and the 723-command "
                "golden benchmark dataset.<br/>"
                "<b>Authored Code Modules:</b><br/>"
                "• <font name='Courier'>src/shellsense/nlp/rule_based.py</font> (Deterministic schema-first rule parser, confidence policy)<br/>"
                "• <font name='Courier'>src/shellsense/nlp/entities.py</font> (Entity extraction: sizes, counts, superlatives, time, file types)<br/>"
                "• <font name='Courier'>src/shellsense/nlp/context.py</font> (SessionContextStore, 10-minute result set caching, follow-ups)<br/>"
                "• <font name='Courier'>tests/nlp/golden_commands.yaml</font> (723 test phrases across all 48 intents)<br/>"
                "• <font name='Courier'>tests/test_golden_commands.py</font> (Golden dataset verification suite with 99.9% accuracy)<br/>"
                "<b>Detailed Technical Explanation:</b><br/>"
                "<i>\"I built the natural language understanding engine that bridges human intent and rigid OS structures. "
                "Recognizing that LLMs can hallucinate commands or bypass security checks, I architected a deterministic, "
                "schema-first parser. In entities.py, I implemented deep normalization: expanding contractions ('what's' -> 'what is'), "
                "translating number words to digits ('ten' -> 10), resolving sizes ('1.5 gigs' -> 1,610,612,736 bytes), and mapping "
                "file type families (documents, spreadsheets, photos, videos) to explicit extension sets. In context.py, I created "
                "the SessionContextStore: when a user asks 'find the largest files in Downloads', the resulting paths are cached server-side. "
                "When the user immediately follows up with 'delete them', 'move those to Backup', or 'zip the first 3', the parser "
                "resolves concrete file paths from server state without ever trusting client input. I also implemented fail-closed "
                "negation detection ('don't delete my reports') which halts before planning. My test suite tests 723 varied phrases, "
                "achieving a verified 99.9% accuracy rate across typos, colloquialisms, and inverted syntax.\"</i>",
                callout_style,
            )
        ],
    ]
    t_p2 = Table(p2_box, colWidths=[504])
    t_p2.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("BACKGROUND", (0, 1), (-1, 1), bg_subtle),
            ("BOX", (0, 0), (-1, -1), 1, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(t_p2)

    story.append(PageBreak())

    # --- PERSON 3 ---
    p3_box = [
        [
            Paragraph(
                "<b>Engineer 3: Operations Engine, Target Resolution & Safe Execution Subsystem</b>",
                table_header_style,
            )
        ],
        [
            Paragraph(
                "<b>Core Role & Systems Owned:</b> Systems Backend Engineer responsible for the Operation Registry, the read-only "
                "Planner, all 27 self-contained Operation implementations across retrieval, file manipulation, archives, and cleanup, "
                "and the sole Executor gate.<br/>"
                "<b>Authored Code Modules:</b><br/>"
                "• <font name='Courier'>src/shellsense/operations/registry.py</font> (BaseOperation abstract protocol & registry)<br/>"
                "• <font name='Courier'>src/shellsense/planner.py</font> (Read-only target resolution and plan construction)<br/>"
                "• <font name='Courier'>src/shellsense/operations/retrieval_ops.py</font> (File search, largest/smallest files, counts, sizes)<br/>"
                "• <font name='Courier'>src/shellsense/operations/file_ops.py</font> (Create, move, copy, rename, trash operations)<br/>"
                "• <font name='Courier'>src/shellsense/operations/archive_ops.py</font> (Zip/tar creation and Zip-Slip defended extraction)<br/>"
                "• <font name='Courier'>src/shellsense/operations/cleanup_ops.py & duplicates.py</font> (Safe temp cleaning & duplicate detection)<br/>"
                "• <font name='Courier'>src/shellsense/operations/process_ops.py & system_info.py</font> (Process & hardware query operations)<br/>"
                "• <font name='Courier'>src/shellsense/operations/meta_ops.py</font> (Help, permissions, history, explain, and undo operations)<br/>"
                "• <font name='Courier'>src/shellsense/executor/executor.py & jobs.py</font> (Sole execution gate, task queue, cancel tokens)<br/>"
                "<b>Detailed Technical Explanation:</b><br/>"
                "<i>\"I engineered the operational core of ShellSense where abstract intentions become safe OS operations. "
                "Under Invariant 2, I prohibited all shell subprocesses; every single operation uses native Python standard library "
                "APIs (pathlib, shutil, psutil, send2trash). In operations/registry.py, I established the strict Operation protocol: "
                "every capability must implement params_schema, compute_risk, plan, preview, execute, and undo. "
                "In archive_ops.py, I built enterprise-grade Zip-Slip protection: every tar and zip entry is checked against canonical "
                "path traversal ('..'), symlink entries are discarded, and bombs are prevented by capping uncompressed size to 2GB and "
                "compression ratio to 100:1. In file_ops.py, deletion routes strictly to send2trash with an undo record recorded in "
                "SQLite. In executor.py, I instituted TOCTOU (Time-of-Check to Time-of-Use) validation: right before performing an action, "
                "the executor re-verifies that the target's physical inode and modification time match what the human approved.\"</i>",
                callout_style,
            )
        ],
    ]
    t_p3 = Table(p3_box, colWidths=[504])
    t_p3.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("BACKGROUND", (0, 1), (-1, 1), bg_subtle),
            ("BOX", (0, 0), (-1, -1), 1, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(t_p3)
    story.append(Spacer(1, 14))

    # --- PERSON 4 ---
    p4_box = [
        [
            Paragraph(
                "<b>Engineer 4: Desktop Application, API Gateway & Frontend User Interface</b>",
                table_header_style,
            )
        ],
        [
            Paragraph(
                "<b>Core Role & Systems Owned:</b> Full-Stack & Desktop Engineer responsible for the hardened local FastAPI server, "
                "the React 18 / TypeScript frontend, desktop window integration (pywebview), real-time WebSocket telemetry, "
                "and the CLI user experience.<br/>"
                "<b>Authored Code Modules:</b><br/>"
                "• <font name='Courier'>src/shellsense/api/app.py & security.py</font> (Localhost API server, session token, CSP headers)<br/>"
                "• <font name='Courier'>src/shellsense/api/routes/*.py</font> (Chat, files, processes, plans, tasks, history, permissions routes)<br/>"
                "• <font name='Courier'>src/shellsense/gui/launcher.py & cli.py</font> (Desktop pywebview launcher, CLI ask with --explain)<br/>"
                "• <font name='Courier'>frontend/src/features/chat/ChatScreen.tsx</font> (Hero card, 'Understood as', collapsible explanation)<br/>"
                "• <font name='Courier'>frontend/src/components/ConfirmationModal.tsx</font> (DESTRUCTIVE action typed confirmation modal)<br/>"
                "• <font name='Courier'>frontend/src/features/monitor/MonitorScreen.tsx</font> (Hardware usage telemetry charts)<br/>"
                "• <font name='Courier'>frontend/src/features/files, processes, tasks, history, settings</font> (Complete 9-screen desktop UI)<br/>"
                "<b>Detailed Technical Explanation:</b><br/>"
                "<i>\"I authored the user-facing presentation and integration layers. Under Invariant 16, the local API is hostile "
                "territory: any web page or malicious software on localhost might attempt to invoke endpoints. I secured the FastAPI gateway "
                "by binding strictly to 127.0.0.1, generating a cryptographically secure 256-bit session token on every launch injected "
                "into the webview DOM, and validating Host and Origin headers to prevent DNS rebinding. In the frontend, I built the "
                "9 distinct screens matching the UI mockups using React, TypeScript, and Tailwind CSS. In ChatScreen.tsx, I implemented "
                "full parsing transparency: every assistant message displays an 'Understood as: ...' header and an expandable "
                "'How I understood this' card showing operation name, confidence %, extracted parameters, defaults, and resolved scope. "
                "For DESTRUCTIVE actions, I built the modal requiring the user to type the exact random confirmation token before dispatching "
                "the approval request. Finally, I added the CLI '--explain' flag so command-line users receive the exact same insight.\"</i>",
                callout_style,
            )
        ],
    ]
    t_p4 = Table(p4_box, colWidths=[504])
    t_p4.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("BACKGROUND", (0, 1), (-1, 1), bg_subtle),
            ("BOX", (0, 0), (-1, -1), 1, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(t_p4)

    story.append(PageBreak())

    # =========================================================================
    # SECTION 4: VERIFICATION, QUALITY METRICS & QUICKSTART
    # =========================================================================
    story.append(Paragraph("4. Testing, Verification & Quickstart Guide", h1_style))
    story.append(
        HRFlowable(
            width="100%", thickness=1, color=indigo_color, spaceAfter=10, spaceBefore=2
        )
    )

    story.append(Paragraph("4.1 Test Verification Suite (70/70 Passing)", h2_style))
    test_summary_text = (
        "The codebase is subjected to end-to-end automated testing covering all layers of the architecture: "
        "API security, approval replay defense, cryptographic audit chaining, path traversal containment, "
        "platform adapter isolation, golden command accuracy, and operational side effects."
    )
    story.append(Paragraph(test_summary_text, body_style))

    test_metrics_data = [
        [
            Paragraph("Test Suite Module", table_header_style),
            Paragraph("Tests", table_header_style),
            Paragraph("Scope & Verification Focus", table_header_style),
            Paragraph("Status", table_header_style),
        ],
        [
            Paragraph("tests/test_golden_commands.py", table_cell_bold),
            Paragraph("4 tests", table_cell_style),
            Paragraph("Verifies 48 intents across 723 phrases; checks >=15 variations per intent; verifies 99.9% accuracy.", table_cell_style),
            Paragraph("PASSED", badge_safe),
        ],
        [
            Paragraph("tests/test_operations_and_transparency.py", table_cell_bold),
            Paragraph("4 tests", table_cell_style),
            Paragraph("Tests chat API transparency ('Understood as', explanation info), file ops, context follow-ups, meta ops.", table_cell_style),
            Paragraph("PASSED", badge_safe),
        ],
        [
            Paragraph("tests/test_api_security.py", table_cell_bold),
            Paragraph("7 tests", table_cell_style),
            Paragraph("Tests session token validation, 401 unauthorized rejection, DNS rebinding, and foreign origin blocking.", table_cell_style),
            Paragraph("PASSED", badge_safe),
        ],
        [
            Paragraph("tests/test_approval.py", table_cell_bold),
            Paragraph("5 tests", table_cell_style),
            Paragraph("Validates plan approval, replay attack prevention, plan hash tampering detection, and 120s expiry.", table_cell_style),
            Paragraph("PASSED", badge_safe),
        ],
        [
            Paragraph("tests/test_path_guard.py", table_cell_bold),
            Paragraph("8 tests", table_cell_style),
            Paragraph("Tests allowed roots boundary, traversal rejection ('..'), symlink escape rejection, and Windows ADS/UNC.", table_cell_style),
            Paragraph("PASSED", badge_safe),
        ],
        [
            Paragraph("tests/test_classifier.py", table_cell_bold),
            Paragraph("23 tests", table_cell_style),
            Paragraph("Validates risk classification matrix (SAFE, MODIFY, DESTRUCTIVE, BLOCKED) and fail-closed defaults.", table_cell_style),
            Paragraph("PASSED", badge_safe),
        ],
        [
            Paragraph("tests/test_consent.py & test_audit.py", table_cell_bold),
            Paragraph("7 tests", table_cell_style),
            Paragraph("Tests locked-by-default behavior, TTY human grant check, git-repo consent rejection, and audit hash chaining.", table_cell_style),
            Paragraph("PASSED", badge_safe),
        ],
        [
            Paragraph("tests/test_nlp.py, executor, models, platform", table_cell_bold),
            Paragraph("12 tests", table_cell_style),
            Paragraph("Tests process parsing, PID protection on Linux/Windows, plan immutability, and package metadata.", table_cell_style),
            Paragraph("PASSED", badge_safe),
        ],
    ]
    t_test_m = Table(test_metrics_data, colWidths=[140, 45, 269, 50])
    t_test_m.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), primary_color),
            ("GRID", (0, 0), (-1, -1), 0.5, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, bg_subtle]),
        ])
    )
    story.append(t_test_m)
    story.append(Spacer(1, 14))

    story.append(Paragraph("4.2 Code Quality & Static Analysis", h2_style))
    qa_text = (
        "• <b>Python Ruff Linter & Formatter:</b> Zero linting errors across 100% of source and test files.<br/>"
        "• <b>Mypy Static Type Checker:</b> Strict type analysis passed across 64 source files (<font name='Courier'>disallow_untyped_defs = true</font>).<br/>"
        "• <b>Frontend Build & Tests:</b> React TypeScript compilation and Vite production bundle passed in 2.5s; Vitest passing.<br/>"
        "• <b>Git Remote:</b> Synchronized with remote repository at <font name='Courier'>https://github.com/vabhijith52-dotcom/ShellSense.git</font>."
    )
    story.append(Paragraph(qa_text, bullet_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("4.3 User & Administrator Quickstart Guide", h2_style))
    quickstart_text = (
        "<b>1. Clone Repository & Setup Virtual Environment:</b><br/>"
        "<font name='Courier'>git clone https://github.com/vabhijith52-dotcom/ShellSense.git<br/>"
        "cd ShellSense && python3 -m venv .venv && source .venv/bin/activate<br/>"
        "pip install -e \".[dev]\"</font><br/><br/>"
        "<b>2. Grant Initial Capabilities (Required live human consent):</b><br/>"
        "<font name='Courier'>shellsense permissions grant</font><br/>"
        "Follow the interactive TTY wizard to enable capabilities (FILES_READ, FILES_MODIFY, SYSTEM_INFO_READ) "
        "and select allowed folder roots (e.g. ~/Downloads, ~/Documents). Confirm by typing 'I GRANT ACCESS'.<br/><br/>"
        "<b>3. Run Natural Language Queries via CLI:</b><br/>"
        "<font name='Courier'>shellsense ask \"Show my RAM usage\" --explain<br/>"
        "shellsense ask \"Find the largest files in Downloads\"<br/>"
        "shellsense ask \"What is using port 8080?\"</font><br/><br/>"
        "<b>4. Launch Desktop GUI Window:</b><br/>"
        "<font name='Courier'>shellsense gui</font><br/>"
        "Launches the native desktop window containing the complete 9-screen interface.<br/><br/>"
        "<b>5. Execute Test Suite:</b><br/>"
        "<font name='Courier'>pytest tests/ -v</font>"
    )
    story.append(Paragraph(quickstart_text, body_style))

    # Build the document using NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF at: {filename}")


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent
    out_pdf = out_dir / "ShellSense_Project_Documentation.pdf"
    build_pdf(str(out_pdf))

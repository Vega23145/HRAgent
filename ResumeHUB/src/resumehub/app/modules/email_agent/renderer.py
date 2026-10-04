"""Template renderer using Mako.

All templates live in the ``templates/`` directory next to this file.
They are plain Markdown files with a ``Subject: …`` line on the first
non-comment non-blank line, then the body.

Variables injected into every template:
    candidate_name  str
    candidate_email str
    role_id         str
    role            dict  (the full job-role document, or {})
    sender_name     str   (from settings / env)
    org_name        str   (from settings / env)

Action-specific extras:
    task_assigned → task_title, task_description, task_instructions, task_deadline
    custom        → subject, body
"""
from __future__ import annotations

from pathlib import Path

from mako.lookup import TemplateLookup  # type: ignore[import-untyped]

_TMPL_DIR = Path(__file__).parent / "templates"

_lookup = TemplateLookup(
    directories=[str(_TMPL_DIR)],
    input_encoding="utf-8",
    output_encoding="utf-8",
    encoding_errors="replace",
)

# Map action names → template file (without extension)
ACTION_TEMPLATES: dict[str, str] = {
    "interview":     "interview.md.mako",
    "task_assigned": "task_assigned.md.mako",
    "rejected":      "rejection.md.mako",
    "hired":         "hired.md.mako",
    "custom":        "custom.md.mako",
}


def render(action: str, ctx: dict) -> tuple[str, str]:
    """Return (subject, body_text) for the given action and context dict."""
    tmpl_name = ACTION_TEMPLATES.get(action)
    if not tmpl_name:
        raise ValueError(f"Unknown action: {action!r}. Available: {sorted(ACTION_TEMPLATES)}")
    tmpl = _lookup.get_template(tmpl_name)
    raw: str = tmpl.render_unicode(**ctx).strip()

    # Parse the Subject line
    lines = raw.splitlines()
    subject = ""
    body_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("Subject:"):
            subject = stripped[len("Subject:"):].strip()
            body_start = i + 1
            break

    body = "\n".join(lines[body_start:]).strip()
    return subject, body


def list_templates() -> list[dict]:
    return [
        {"action": action, "file": fname, "path": str(_TMPL_DIR / fname)}
        for action, fname in ACTION_TEMPLATES.items()
    ]

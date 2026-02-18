"""
Public wizard blueprint — adds ``/public`` routes for the guided,
no-freeform-chat wizard.

This restricted mode lets users build markdown or copilot-agent
configurations via structured question cards. Freeform chat is
disabled to prevent misuse.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path

from quart import Blueprint, request, jsonify, send_from_directory

from .auth import require_auth, is_oauth_configured, get_github_token

logger = logging.getLogger(__name__)

_PKG_DIR = Path(__file__).resolve().parent

public_bp = Blueprint(
    "public_wizard",
    __name__,
    static_folder=str(_PKG_DIR / "static"),
    template_folder=str(_PKG_DIR / "templates_html"),
    url_prefix="/public",
)

# ── Rate-limit state (simple IP-based, in-memory) ────────────────────
_rate_limit_window: dict[str, list[float]] = {}  # IP -> list of timestamps
RATE_LIMIT_MAX = int(os.environ.get("SCIAGENT_RATE_LIMIT_MAX", "10"))
RATE_LIMIT_WINDOW_SECS = int(os.environ.get("SCIAGENT_RATE_LIMIT_WINDOW", "3600"))


def _check_rate_limit(ip: str) -> bool:
    """Return True if the request should be allowed."""
    import time

    now = time.time()
    window = _rate_limit_window.setdefault(ip, [])
    # Prune old entries
    cutoff = now - RATE_LIMIT_WINDOW_SECS
    _rate_limit_window[ip] = [t for t in window if t > cutoff]
    window = _rate_limit_window[ip]
    if len(window) >= RATE_LIMIT_MAX:
        return False
    window.append(now)
    return True


@public_bp.route("/")
@require_auth
async def public_index():
    """Serve the public guided wizard page."""
    return await send_from_directory(public_bp.template_folder, "public_wizard.html")


@public_bp.route("/api/start", methods=["POST"])
@require_auth
async def public_start():
    """Accept guided wizard form input and return a session ID + kickoff prompt.

    Validates rate limiting and builds an enriched kickoff prompt from
    the expanded form fields (domain, data types, analysis goals,
    experience level, file types, known packages).
    """
    # Rate limiting
    ip = request.remote_addr or "unknown"
    if not _check_rate_limit(ip):
        return jsonify({
            "error": "Rate limit exceeded. Please try again later."
        }), 429

    data = await request.get_json(silent=True) or {}

    session_id = str(uuid.uuid4())
    domain_description = data.get("domain_description", "")
    research_goals = data.get("research_goals", [])
    data_types = data.get("data_types", [])
    analysis_goals = data.get("analysis_goals", [])
    experience_level = data.get("experience_level", "beginner")
    file_types = data.get("file_types", [])
    known_packages = data.get("known_packages", [])

    # Build an enriched kickoff prompt with all form data
    prompt_parts = []

    if domain_description:
        prompt_parts.append(
            f"The researcher describes their domain as:\n\n"
            f'"{domain_description}"'
        )

    if data_types:
        prompt_parts.append(
            f"They work with these types of data: {', '.join(data_types)}"
        )

    if analysis_goals:
        goals_str = "\n".join(f"- {g}" for g in analysis_goals)
        prompt_parts.append(f"Their analysis goals include:\n{goals_str}")

    if research_goals:
        rg_str = "\n".join(f"- {g}" for g in research_goals)
        prompt_parts.append(f"Additional research goals:\n{rg_str}")

    if experience_level:
        prompt_parts.append(
            f"Their Python experience level is: {experience_level}"
        )

    if file_types:
        prompt_parts.append(
            f"They work with these file formats: {', '.join(file_types)}"
        )

    if known_packages:
        prompt_parts.append(
            f"They already know about / use these packages: {', '.join(known_packages)}"
        )

    prompt_parts.append(
        "This is a GUIDED public session. The user has already provided all "
        "of the above information via the intake form. Do NOT re-ask for it. "
        "Proceed directly with discovery and recommendations using "
        "present_question for all user interactions."
    )

    kickoff_prompt = "\n\n".join(prompt_parts)

    return jsonify({
        "session_id": session_id,
        "kickoff_prompt": kickoff_prompt,
    })


@public_bp.route("/static/<path:filename>")
async def public_static(filename):
    """Serve public-wizard-specific static assets."""
    return await send_from_directory(public_bp.static_folder, filename)

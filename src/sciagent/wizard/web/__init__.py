"""
Wizard web blueprint — adds ``/wizard`` routes to the Quart app.

Provides a multi-step form for initial domain input + example data
upload, then hands off to the standard WebSocket chat for conversational
refinement.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from quart import Blueprint, request, jsonify, send_from_directory

logger = logging.getLogger(__name__)

wizard_bp = Blueprint(
    "wizard",
    __name__,
    static_folder=str(Path(__file__).parent / "static"),
    template_folder=str(Path(__file__).parent / "templates"),
    url_prefix="/wizard",
)


@wizard_bp.route("/")
async def wizard_index():
    """Serve the wizard form page."""
    return await send_from_directory(wizard_bp.template_folder, "wizard.html")


@wizard_bp.route("/api/start", methods=["POST"])
async def wizard_start():
    """Accept initial wizard input and return a session ID.

    The frontend collects domain description + optional file uploads
    in this initial form step. The response includes a session ID
    that the chat WebSocket uses to carry the wizard state.
    """
    data = await request.get_json(silent=True) or {}

    session_id = str(uuid.uuid4())
    domain_description = data.get("domain_description", "")
    research_goals = data.get("research_goals", [])
    file_types = data.get("file_types", [])
    known_packages = data.get("known_packages", [])

    # Build a kickoff prompt the wizard agent will receive
    prompt_parts = []
    if domain_description:
        prompt_parts.append(
            f"The researcher describes their domain as:\n\n"
            f'"{domain_description}"'
        )
    if research_goals:
        goals = "\n".join(f"- {g}" for g in research_goals)
        prompt_parts.append(f"Their research goals are:\n{goals}")
    if file_types:
        prompt_parts.append(f"They work with these file types: {', '.join(file_types)}")
    if known_packages:
        prompt_parts.append(
            f"They already know about / use these packages: {', '.join(known_packages)}"
        )

    kickoff_prompt = "\n\n".join(prompt_parts) if prompt_parts else (
        "Hi! I'd like to build a domain-specific agent. Please interview me about my field."
    )

    return jsonify({
        "session_id": session_id,
        "kickoff_prompt": kickoff_prompt,
    })


@wizard_bp.route("/static/<path:filename>")
async def wizard_static(filename):
    """Serve wizard-specific static assets."""
    return await send_from_directory(wizard_bp.static_folder, filename)

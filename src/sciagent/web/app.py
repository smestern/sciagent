"""
BaseWebApp — Quart-based web chat UI for scientific agents.

Provides the full WebSocket streaming infrastructure.  Domain agents
customise via ``AgentConfig`` (title, file types, suggestion chips, etc.).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from quart import Quart, websocket, request, jsonify, send_from_directory
from quart_cors import cors

from sciagent.web.figure_queue import (
    register_session,
    unregister_session,
    set_current_session,
    get_figures,
)
from sciagent.config import AgentConfig

logger = logging.getLogger(__name__)


def create_app(
    agent_factory: Callable,
    config: Optional[AgentConfig] = None,
    sample_dir: Optional[Path] = None,
) -> Quart:
    """Create and configure the Quart application.

    Args:
        agent_factory: Callable ``(output_dir=...) -> BaseScientificAgent``.
        config: Agent configuration for branding / accepted files.
        sample_dir: Directory containing bundled sample files.

    Returns:
        Configured Quart app.
    """
    config = config or AgentConfig()

    app = Quart(
        __name__,
        static_folder=str(Path(__file__).parent / "static"),
        template_folder=str(Path(__file__).parent / "templates"),
    )
    app = cors(app, allow_origin="*")
    app.ws_sessions: dict = {}  # type: ignore[attr-defined]
    _session_agents: dict = {}  # ws_id -> agent instance
    _session_output_dirs: dict = {}  # ws_id -> output_dir Path

    # ── Config endpoint (used by chat.js) ─────────────────────────
    @app.route("/api/config")
    async def api_config():
        return jsonify({
            "name": config.name,
            "display_name": config.display_name,
            "description": config.description,
            "logo_emoji": config.logo_emoji,
            "accent_color": config.accent_color,
            "github_url": config.github_url,
            "accepted_file_types": config.accepted_file_types,
            "suggestion_chips": [
                {"label": c.label, "prompt": c.prompt}
                for c in config.suggestion_chips
            ],
        })

    # ── Static pages ──────────────────────────────────────────────
    @app.route("/")
    async def index():
        return await send_from_directory(app.template_folder, "index.html")

    # ── Sample files ──────────────────────────────────────────────
    @app.route("/api/samples")
    async def list_samples():
        sdir = sample_dir or _default_sample_dir()
        if not sdir.exists():
            return jsonify({"samples": []})
        ext_set = set(config.accepted_file_types)
        samples = []
        for f in sorted(sdir.iterdir()):
            if f.suffix.lower() in ext_set and f.is_file():
                samples.append({
                    "name": f.name,
                    "size_kb": round(f.stat().st_size / 1024, 1),
                })
        return jsonify({"samples": samples})

    @app.route("/api/load-sample", methods=["POST"])
    async def load_sample():
        data = await request.get_json()
        sample_name = data.get("name", "")
        session_id = data.get("session_id", "")
        sdir = sample_dir or _default_sample_dir()
        src = sdir / sample_name
        ext_set = set(config.accepted_file_types)
        if not src.exists() or src.suffix.lower() not in ext_set:
            return jsonify({"error": "Sample not found"}), 404
        dest_dir = _session_dir(session_id)
        dest = dest_dir / sample_name
        shutil.copy2(src, dest)
        return jsonify({"file_id": sample_name, "path": str(dest)})

    # ── File upload ───────────────────────────────────────────────
    @app.route("/upload", methods=["POST"])
    async def upload_file():
        files = await request.files
        uploaded = files.get("file")
        if uploaded is None:
            return jsonify({"error": "No file provided"}), 400
        fname = uploaded.filename or "upload"
        ext_set = set(config.accepted_file_types)
        if not any(fname.lower().endswith(e) for e in ext_set):
            return jsonify({
                "error": f"Only {', '.join(ext_set)} files are supported"
            }), 400
        session_id = (await request.form).get("session_id", str(uuid.uuid4()))
        dest_dir = _session_dir(session_id)
        dest = dest_dir / fname
        await uploaded.save(str(dest))
        return jsonify({"file_id": fname, "path": str(dest), "session_id": session_id})

    # ── Export reproducible script ────────────────────────────────
    @app.route("/api/export-script")
    async def export_script():
        """Download the most recent reproducible script for a session."""
        session_id = request.args.get("session_id", "")
        if not session_id or session_id not in _session_output_dirs:
            return jsonify({"error": "Unknown session"}), 404
        out_dir = _session_output_dirs[session_id]
        # Look for the reproducible script
        script = out_dir / "reproducible_analysis.py"
        if not script.exists():
            # Try any .py file in the top-level output dir
            py_files = list(out_dir.glob("*.py"))
            if py_files:
                script = py_files[0]
            else:
                return jsonify({"error": "No script has been exported yet. Use /export or ask the agent to produce one."}), 404
        return await send_from_directory(
            str(script.parent), script.name,
            as_attachment=True,
            attachment_filename=script.name,
        )

    # ── WebSocket chat ────────────────────────────────────────────
    @app.websocket("/ws/chat")
    async def ws_chat():
        ws_id = str(uuid.uuid4())
        agent = None
        session = None
        output_dir = _session_dir(ws_id)
        register_session(ws_id)
        _session_output_dirs[ws_id] = output_dir

        send_queue: asyncio.Queue = asyncio.Queue()

        async def _drain_queue():
            while True:
                msg = await send_queue.get()
                if msg is None:
                    break
                try:
                    await websocket.send(json.dumps(msg))
                except Exception:
                    break

        async def _drain_figure_queue():
            while True:
                await asyncio.sleep(0.1)
                figures = get_figures(ws_id)
                for fig in figures:
                    if isinstance(fig, dict) and "image_base64" in fig:
                        try:
                            await websocket.send(json.dumps({
                                "type": "figure",
                                "data": fig["image_base64"],
                                "figure_number": fig.get("figure_number", 0),
                            }))
                        except Exception:
                            break

        drain_task = asyncio.ensure_future(_drain_queue())
        figure_drain_task = asyncio.ensure_future(_drain_figure_queue())

        try:
            from sciagent.tools.code_tools import set_output_dir

            agent = agent_factory(output_dir=output_dir)
            _session_agents[ws_id] = agent
            set_output_dir(output_dir)

            send_queue.put_nowait({"type": "status", "text": "Starting agent…"})
            await agent.start()

            session = await agent.create_session()
            send_queue.put_nowait({
                "type": "connected",
                "session_id": ws_id,
                "text": f"{config.display_name} ready. Ask me anything about your data!",
            })

            while True:
                raw = await websocket.receive()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    msg = {"text": raw}

                user_text = msg.get("text", "").strip()
                if not user_text:
                    continue

                file_id = msg.get("file_id")
                if file_id:
                    full_path = output_dir / file_id
                    if full_path.exists():
                        user_text = f"Load the file at {full_path} and then: {user_text}"

                set_current_session(ws_id)
                await _stream_response(session, user_text, output_dir, send_queue)
                set_current_session(None)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception("WebSocket error")
            try:
                send_queue.put_nowait({"type": "error", "text": str(e)})
            except Exception:
                pass
        finally:
            set_current_session(None)
            unregister_session(ws_id)
            _session_agents.pop(ws_id, None)
            _session_output_dirs.pop(ws_id, None)
            send_queue.put_nowait(None)
            drain_task.cancel()
            figure_drain_task.cancel()
            if agent:
                try:
                    await agent.stop()
                except Exception:
                    pass

    return app


# ── Streaming helper ────────────────────────────────────────────────────

async def _stream_response(
    session, prompt: str, output_dir: Path,
    send_queue: asyncio.Queue, timeout: float = 600,
):
    """Send a prompt and stream events back via the queue."""
    from copilot.generated.session_events import SessionEventType

    idle_event = asyncio.Event()
    response_text_parts: list[str] = []

    def _enqueue(msg: dict):
        try:
            send_queue.put_nowait(msg)
        except Exception:
            pass

    def _handler(event):
        etype = event.type

        if etype == SessionEventType.ASSISTANT_REASONING_DELTA:
            delta = getattr(event.data, "delta_content", None) or ""
            if delta:
                _enqueue({"type": "thinking", "text": delta})

        elif etype == SessionEventType.ASSISTANT_REASONING:
            text = getattr(event.data, "reasoning_text", None) or ""
            if text:
                _enqueue({"type": "thinking", "text": text})

        elif etype == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            delta = getattr(event.data, "delta_content", None) or ""
            if delta:
                response_text_parts.append(delta)
                _enqueue({"type": "text_delta", "text": delta})

        elif etype == SessionEventType.ASSISTANT_MESSAGE:
            _enqueue_figures(event, output_dir, _enqueue)
            if not response_text_parts:
                content = _extract_content(event)
                if content:
                    _enqueue({"type": "text_delta", "text": content})

        elif etype == SessionEventType.TOOL_EXECUTION_START:
            name = getattr(event.data, "tool_name", "tool")
            _enqueue({"type": "tool_start", "name": name})

        elif etype == SessionEventType.TOOL_EXECUTION_COMPLETE:
            name = getattr(event.data, "tool_name", "tool")
            _enqueue({"type": "tool_complete", "name": name})
            _extract_figures_from_tool_event(event, _enqueue)

        elif etype == SessionEventType.SESSION_ERROR:
            err = getattr(event.data, "message", str(event.data))
            _enqueue({"type": "error", "text": err})
            idle_event.set()

        elif etype == SessionEventType.SESSION_IDLE:
            idle_event.set()

    unsub = session.on(_handler)
    try:
        await session.send({"prompt": prompt})
        try:
            await asyncio.wait_for(idle_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            _enqueue({"type": "error", "text": "Response timed out."})
    finally:
        unsub()

    _enqueue({"type": "done"})
    await asyncio.sleep(0.05)


def _enqueue_figures(event, output_dir, enqueue_fn):
    tool_results = getattr(event, "tool_results", None)
    if not tool_results and hasattr(event, "data"):
        tool_results = getattr(event.data, "tool_results", None)
    if not tool_results:
        return
    items = tool_results if isinstance(tool_results, list) else [tool_results]
    for tr in items:
        if not isinstance(tr, dict):
            continue
        for fig in tr.get("figures", []):
            if isinstance(fig, dict) and "image_base64" in fig:
                enqueue_fn({
                    "type": "figure",
                    "data": fig["image_base64"],
                    "figure_number": fig.get("figure_number", 0),
                })


def _extract_figures_from_tool_event(event, enqueue_fn):
    result = None
    if hasattr(event, "data"):
        for attr in ("result", "tool_result", "output", "content"):
            result = getattr(event.data, attr, None)
            if result is not None:
                break
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            pass
    if not isinstance(result, dict):
        return
    for fig in result.get("figures", []):
        if isinstance(fig, dict) and "image_base64" in fig:
            enqueue_fn({
                "type": "figure",
                "data": fig["image_base64"],
                "figure_number": fig.get("figure_number", 0),
            })


def _extract_content(event) -> Optional[str]:
    if hasattr(event, "data") and hasattr(event.data, "content"):
        return event.data.content
    if isinstance(event, dict):
        return event.get("content") or event.get("message")
    return None


# ── Helpers ─────────────────────────────────────────────────────────────

def _default_sample_dir() -> Path:
    return Path.cwd() / "data" / "samples"


def _session_dir(session_id: str) -> Path:
    d = Path(tempfile.gettempdir()) / "sciagent_web" / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def main():
    """Standalone entry — override this in your domain agent's CLI."""
    print("Use your domain agent's web command instead.")
    print("sciagent.web.app.create_app() is a factory, not a standalone server.")

"""
BaseWebApp — Quart-based web chat UI for scientific agents.

Provides the full WebSocket streaming infrastructure.  Domain agents
customise via ``AgentConfig`` (title, file types, suggestion chips, etc.).
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set

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
    public_agent_factory: Optional[Callable] = None,
) -> Quart:
    """Create and configure the Quart application.

    Args:
        agent_factory: Callable ``(output_dir=...) -> BaseScientificAgent``.
        config: Agent configuration for branding / accepted files.
        sample_dir: Directory containing bundled sample files.
        public_agent_factory: Optional callable for public/guided-mode
            sessions. If provided, the public wizard blueprint is
            registered and uses this factory for WebSocket sessions
            starting from ``/public``.

    Returns:
        Configured Quart app.
    """
    config = config or AgentConfig()

    app = Quart(
        __name__,
        static_folder=str(Path(__file__).parent / "static"),
        template_folder=str(Path(__file__).parent / "templates"),
    )

    # ── CORS — restrict when OAuth is enabled ─────────────────────
    _cors_origin = os.environ.get("SCIAGENT_ALLOWED_ORIGINS", "*")
    app = cors(app, allow_origin=_cors_origin)

    # ── OAuth session support (opt-in) ────────────────────────────
    try:
        from sciagent_wizard.auth import (
            is_oauth_configured,
            configure_app_sessions,
            create_auth_blueprint,
        )

        configure_app_sessions(app)
        if is_oauth_configured() or os.environ.get("SCIAGENT_INVITE_CODE"):
            app.register_blueprint(create_auth_blueprint())
    except ImportError:
        pass  # wizard package not installed

    app.ws_sessions: dict = {}  # type: ignore[attr-defined]
    _session_agents: dict = {}  # ws_id -> agent instance
    _session_output_dirs: dict = {}  # ws_id -> output_dir Path
    # Track which sessions use the public factory
    _public_sessions: Set[str] = set()

    # ── Register wizard blueprint ─────────────────────────────────
    try:
        from sciagent_wizard.web import wizard_bp
        app.register_blueprint(wizard_bp)
    except ImportError:
        pass  # wizard dependencies not installed

    # ── Register public wizard blueprint ──────────────────────────
    if public_agent_factory is not None:
        try:
            from sciagent_wizard.public import public_bp
            app.register_blueprint(public_bp)
        except ImportError:
            pass

        # ── Override /wizard routes to redirect to /public ────────
        @app.route("/wizard/")
        @app.route("/wizard")
        async def wizard_redirect_to_public():
            from quart import redirect
            return redirect("/public/")

        @app.route("/wizard/api/start", methods=["POST"])
        async def wizard_api_redirect_to_public():
            from quart import redirect
            return redirect("/public/api/start", code=307)

    # ── Register docs ingestor blueprint ──────────────────────────
    try:
        from sciagent_wizard.docs_ingestor.web import ingestor_bp
        app.register_blueprint(ingestor_bp)
    except ImportError:
        pass  # docs ingestor dependencies not installed

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
            "rigor_level": config.rigor_level,
            "suggestion_chips": [
                {"label": c.label, "prompt": c.prompt}
                for c in config.suggestion_chips
            ],
        })

    @app.route("/api/config/rigor", methods=["POST"])
    async def api_set_rigor():
        """Change the rigor enforcement level at runtime."""
        from sciagent.guardrails.scanner import RigorLevel
        from sciagent.tools.context import get_active_context

        body = await request.get_json(silent=True) or {}
        level_str = body.get("rigor_level", "").strip().lower()
        if level_str not in ("strict", "standard", "relaxed", "bypass"):
            return jsonify({"error": f"Invalid rigor_level: {level_str!r}"}), 400

        config.rigor_level = level_str  # persist on config object
        ctx = get_active_context()
        if ctx and ctx.scanner:
            ctx.scanner.rigor_level = RigorLevel.from_str(level_str)

        logger.info("Rigor level changed to %s", level_str)
        return jsonify({"rigor_level": level_str})

    # ── Static pages ──────────────────────────────────────────────
    @app.route("/")
    async def index():
        if public_agent_factory is not None:
            from quart import redirect
            return redirect("/public/")
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

    # ── Serve files from session output directories ──────────────
    @app.route("/api/session-files/<session_id>/<path:filename>")
    async def session_files(session_id: str, filename: str):
        """Serve files (e.g. saved PNGs) from a session's output dir."""
        out_dir = _session_output_dirs.get(session_id)
        if not out_dir or not out_dir.exists():
            return jsonify({"error": "Unknown session"}), 404
        # Search output dir and immediate subdirs for the file
        target = out_dir / filename
        if not target.exists():
            for child in out_dir.rglob(filename):
                target = child
                break
        if not target.exists() or not target.is_file():
            return jsonify({"error": "File not found"}), 404
        return await send_from_directory(str(target.parent), target.name)

    # ── Download generated project as zip ─────────────────────────
    @app.route("/api/download-project/<session_id>")
    async def download_project(session_id: str):
        """Zip and download the generated agent project for a session."""
        out_dir = _session_output_dirs.get(session_id)
        if not out_dir or not out_dir.exists():
            return jsonify({"error": "Unknown session"}), 404
        # Find the project directory (generated by the wizard)
        agent = _session_agents.get(session_id)
        project_dir = None
        if agent:
            ws = getattr(agent, '_wizard_state', None)
            if ws and ws.project_dir:
                project_dir = Path(ws.project_dir)
        # Fallback: look for subdirectories in the output dir
        if not project_dir or not project_dir.exists():
            subdirs = [
                d for d in out_dir.iterdir()
                if d.is_dir() and not d.name.startswith('.')
            ]
            if subdirs:
                project_dir = subdirs[0]
            else:
                project_dir = out_dir
        # Build zip in memory
        import zipfile
        buf = io.BytesIO()
        project_name = project_dir.name or "sciagent-project"
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for fpath in project_dir.rglob('*'):
                if fpath.is_file():
                    arcname = f"{project_name}/{fpath.relative_to(project_dir)}"
                    zf.write(fpath, arcname)
        buf.seek(0)
        zip_bytes = buf.getvalue()

        # ── Clean up generated files after building zip ────
        # The zip is fully in memory so it's safe to remove the
        # project directory (and session output dir) now to free
        # disk space on the server.
        try:
            if project_dir and project_dir.exists():
                shutil.rmtree(project_dir, ignore_errors=True)
                logger.info(
                    "Cleaned up project dir after zip download: %s",
                    project_dir,
                )
        except Exception as cleanup_err:
            logger.warning(
                "Failed to clean project dir %s: %s",
                project_dir, cleanup_err,
            )
        try:
            out_dir = _session_output_dirs.get(session_id)
            if out_dir and out_dir.exists():
                shutil.rmtree(out_dir, ignore_errors=True)
                logger.info(
                    "Cleaned up session output dir after zip download: %s",
                    out_dir,
                )
            _session_output_dirs.pop(session_id, None)
            _session_agents.pop(session_id, None)
        except Exception as cleanup_err:
            logger.warning(
                "Failed to clean session data for %s: %s",
                session_id, cleanup_err,
            )

        from quart import Response
        return Response(
            zip_bytes,
            mimetype='application/zip',
            headers={
                'Content-Disposition':
                    f'attachment; filename="{project_name}.zip"'
            },
        )

    # ── Export reproducible script ────────────────────────────────
    @app.route("/api/export-script")
    async def export_script():
        """Download the most recent reproducible script for a session."""
        session_id = request.args.get("session_id", "")
        if not session_id or session_id not in _session_output_dirs:
            return jsonify({"error": "Unknown session"}), 404
        out_dir = _session_output_dirs[session_id]
        script = out_dir / "reproducible_analysis.py"
        if not script.exists():
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
        # Block the normal chat endpoint when running in public-only mode
        if public_agent_factory is not None:
            await websocket.accept()
            await websocket.send(json.dumps({
                "type": "error",
                "text": "This instance is running in public mode. Please use /public/ instead.",
            }))
            return
        await _run_ws_session(
            factory=agent_factory,
            config=config,
            watch_pngs=True,
            agents=_session_agents,
            output_dirs=_session_output_dirs,
        )

    # ── Public WebSocket chat (guided mode) ───────────────────────
    if public_agent_factory is not None:
        @app.websocket("/ws/public-chat")
        async def ws_public_chat():
            """WebSocket for public guided-mode sessions."""
            await _run_ws_session(
                factory=public_agent_factory,
                config=config,
                watch_pngs=False,
                agents=_session_agents,
                output_dirs=_session_output_dirs,
            )

    return app


# ── Shared WebSocket handler ───────────────────────────────────────────


async def _run_ws_session(
    *,
    factory: Callable,
    config: AgentConfig,
    watch_pngs: bool,
    agents: dict,
    output_dirs: dict,
) -> None:
    """Common WebSocket session loop used by both normal and public chat.

    Args:
        factory: Agent factory ``(output_dir=...) -> BaseScientificAgent``.
        config: Agent branding / config.
        watch_pngs: If True, watch output_dir for new PNG files and push them.
        agents: Mutable dict tracking ``ws_id -> agent`` for the app.
        output_dirs: Mutable dict tracking ``ws_id -> output_dir`` for the app.
    """
    ws_id = str(uuid.uuid4())
    agent = None
    session = None
    output_dir = _session_dir(ws_id)
    register_session(ws_id)
    output_dirs[ws_id] = output_dir

    send_queue: asyncio.Queue = asyncio.Queue()
    background_tasks: list[asyncio.Task] = []

    # ── Queue sender ──────────────────────────────────────────────
    async def _drain_queue():
        while True:
            msg = await send_queue.get()
            if msg is None:
                break
            try:
                await websocket.send(json.dumps(msg))
            except Exception:
                break

    background_tasks.append(asyncio.ensure_future(_drain_queue()))

    # ── Optional background watchers ──────────────────────────────
    if watch_pngs:
        async def _drain_figure_queue():
            while True:
                await asyncio.sleep(0.3)
                _ = get_figures(ws_id)

        async def _watch_png_files():
            known: Set[Path] = set()
            counter = 1000
            while True:
                await asyncio.sleep(0.5)
                try:
                    if not output_dir.exists():
                        continue
                    current = set(output_dir.rglob("*.png"))
                    for png in sorted(current - known):
                        try:
                            b64 = base64.b64encode(png.read_bytes()).decode()
                            await websocket.send(json.dumps({
                                "type": "figure",
                                "data": b64,
                                "figure_number": counter,
                                "filename": png.name,
                            }))
                            counter += 1
                        except Exception:
                            break
                    known = current
                except Exception as exc:
                    logger.debug("PNG watcher error: %s", exc)

        background_tasks.append(asyncio.ensure_future(_drain_figure_queue()))
        background_tasks.append(asyncio.ensure_future(_watch_png_files()))

    # ── Main conversation loop ────────────────────────────────────
    try:
        from sciagent.tools.code_tools import set_output_dir

        # ── Extract GitHub token from session (if OAuth enabled) ──
        _github_token = None
        try:
            from sciagent_wizard.auth import get_github_token
            _github_token = get_github_token()
        except ImportError:
            pass

        # ── Fallback: use service token for invite-code users ─────
        if not _github_token:
            _github_token = os.environ.get("SCIAGENT_SERVICE_TOKEN")

        agent = factory(output_dir=output_dir, github_token=_github_token)
        agents[ws_id] = agent
        set_output_dir(output_dir)

        # ── Apply model selection from query params (for billing) ──
        try:
            model_param = websocket.args.get("model")
            if model_param:
                wizard_state = getattr(agent, "_wizard_state", None)
                if wizard_state is not None:
                    from sciagent_wizard.models import SUPPORTED_MODELS
                    if model_param in SUPPORTED_MODELS:
                        wizard_state.model = model_param
                        logger.info("Set wizard model to %s", model_param)
        except Exception as e:
            logger.debug("Could not set model from query param: %s", e)

        is_guided = getattr(agent, "_guided_mode", False)
        kickoff_received = False

        send_queue.put_nowait({"type": "status", "text": "Starting agent\u2026"})
        await agent.start()

        session = await agent.create_session(session_id=ws_id)
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

            msg_type = msg.get("type", "chat")

            # ── Guided-mode enforcement ──────────────────────
            if is_guided:
                user_text = _handle_guided_message(
                    msg, msg_type, agent, send_queue, kickoff_received,
                )
                if user_text is None:
                    continue
                if not kickoff_received and msg_type != "question_response":
                    kickoff_received = True
            else:
                user_text = msg.get("text", "").strip()

            if not user_text:
                continue

            file_id = msg.get("file_id")
            if file_id:
                full_path = output_dir / file_id
                if full_path.exists():
                    user_text = f"Load the file at {full_path} and then: {user_text}"

            set_current_session(ws_id)
            try:
                await stream_response(
                    session, user_text, send_queue,
                    session_id=ws_id, agent=agent,
                )
            except Exception as send_err:
                if "Session not found" in str(send_err):
                    logger.warning("Session expired, attempting to resume\u2026")
                    send_queue.put_nowait({
                        "type": "status", "text": "Session expired \u2014 reconnecting\u2026",
                    })
                    try:
                        session = await agent.resume_session(ws_id)
                    except Exception:
                        session = await agent.create_session(session_id=ws_id)
                    await stream_response(
                        session, user_text, send_queue,
                        session_id=ws_id, agent=agent,
                    )
                else:
                    raise
            set_current_session(None)

    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.exception("WebSocket error")
        try:
            send_queue.put_nowait({"type": "error", "text": str(exc)})
        except Exception:
            pass
    finally:
        set_current_session(None)
        unregister_session(ws_id)
        agents.pop(ws_id, None)
        output_dirs.pop(ws_id, None)
        send_queue.put_nowait(None)
        for task in background_tasks:
            task.cancel()
        if session:
            try:
                await agent.destroy_session(ws_id)
            except Exception:
                pass
        if agent:
            try:
                await agent.stop()
            except Exception:
                pass
        # ── Clean up session temp directory from disk ─────────
        try:
            if output_dir and output_dir.exists():
                shutil.rmtree(output_dir, ignore_errors=True)
                logger.info(
                    "Cleaned up session temp dir on disconnect: %s",
                    output_dir,
                )
        except Exception as cleanup_err:
            logger.warning(
                "Failed to clean temp dir %s: %s",
                output_dir, cleanup_err,
            )


def _handle_guided_message(
    msg: dict,
    msg_type: str,
    agent,
    send_queue: asyncio.Queue,
    kickoff_received: bool,
) -> Optional[str]:
    """Process a message under guided-mode rules.

    Returns the user text to send, or ``None`` to skip this message.
    """
    wizard_state = getattr(agent, "_wizard_state", None)

    if msg_type == "question_response":
        answer = msg.get("answer", "").strip()
        pending = wizard_state.pending_question if wizard_state else None
        if pending:
            if not pending.allow_freetext and pending.options:
                if pending.allow_multiple:
                    answers = [a.strip() for a in answer.split(",")]
                    valid = all(a in pending.options for a in answers)
                else:
                    valid = answer in pending.options
                if not valid:
                    send_queue.put_nowait({
                        "type": "error",
                        "text": "Please select one of the provided options.",
                    })
                    return None
            if pending.allow_freetext and len(answer) > pending.max_length:
                send_queue.put_nowait({
                    "type": "error",
                    "text": f"Response too long (max {pending.max_length} characters).",
                })
                return None
            wizard_state.pending_question = None
        return answer

    if not kickoff_received:
        text = msg.get("text", "").strip()
        return text if text else None

    # Reject freeform chat in guided mode
    send_queue.put_nowait({
        "type": "error",
        "text": "Please use the provided options to respond.",
    })
    return None


# ── Streaming helper ────────────────────────────────────────────────────


async def stream_response(
    session,
    user_text: str,
    send_queue: asyncio.Queue,
    *,
    session_id: str = "",
    agent: Any = None,
    _retry: int = 0,
) -> None:
    """Send *user_text* to the agent session and stream events via *send_queue*.

    Mirrors the CLI's ``_stream_and_print`` but pushes structured dicts
    into a queue that the WebSocket drain loop sends to the browser.
    """
    # Access wizard state if available (for guided-mode question cards)
    wizard_state = getattr(agent, "_wizard_state", None)
    logger.info(
        "[stream] wizard_state=%s, agent type=%s",
        "present" if wizard_state else "NONE",
        type(agent).__name__ if agent else "None",
    )
    from copilot.generated.session_events import SessionEventType

    MAX_RETRIES = 2
    idle_event = asyncio.Event()
    transient_error: list[str] = []  # use list to allow mutation in closure

    # Track tool names from START events — the SDK's
    # TOOL_EXECUTION_COMPLETE event often has tool_name=None.
    _active_tools: dict[str, str] = {}  # tool_call_id → tool_name

    def _handler(event):
        etype = event.type
        logger.debug("[stream] event type=%s", etype)

        if etype == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            delta = getattr(event.data, "delta_content", None) or ""
            if delta:
                send_queue.put_nowait({"type": "text_delta", "text": delta})

        elif etype == SessionEventType.ASSISTANT_REASONING_DELTA:
            delta = getattr(event.data, "delta_content", None) or ""
            if delta:
                send_queue.put_nowait({"type": "thinking", "text": delta})

        elif etype == SessionEventType.ASSISTANT_MESSAGE:
            content = None
            if hasattr(event, "data") and hasattr(event.data, "content"):
                content = event.data.content
            if content and content.strip():
                # Suppress forwarding raw question_card JSON as plain
                # text — the card is already sent from
                # _maybe_forward_question_card on TOOL_EXECUTION_COMPLETE.
                _is_qcard = False
                try:
                    import json as _json
                    _parsed = _json.loads(content)
                    if isinstance(_parsed, dict) and _parsed.get(
                        "__type__"
                    ) == "question_card":
                        _is_qcard = True
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass
                if not _is_qcard:
                    send_queue.put_nowait({"type": "message", "text": content})

        elif etype == SessionEventType.TOOL_EXECUTION_START:
            name = getattr(event.data, "tool_name", None) or "tool"
            call_id = getattr(event.data, "tool_call_id", None)
            if call_id and name != "tool":
                _active_tools[call_id] = name
            logger.info(
                "[stream] TOOL_START: %s (call_id=%s)", name, call_id,
            )
            send_queue.put_nowait({"type": "tool_start", "name": name})

        elif etype == SessionEventType.TOOL_EXECUTION_COMPLETE:
            raw_name = getattr(event.data, "tool_name", None)
            call_id = getattr(event.data, "tool_call_id", None)
            # Resolve tool name: prefer event data, fall back to
            # tracked name from START event, then "tool".
            name = (
                raw_name
                or _active_tools.pop(call_id, None)
                if call_id else raw_name
            ) or "tool"
            logger.info(
                "[stream] TOOL_COMPLETE: %s "
                "(raw_name=%s, call_id=%s) | "
                "wizard_state=%s | "
                "pending_question=%s",
                name, raw_name, call_id,
                "present" if wizard_state else "NONE",
                repr(getattr(
                    wizard_state, "pending_question", "N/A"
                ))[:200] if wizard_state else "N/A",
            )
            send_queue.put_nowait({"type": "tool_complete", "name": name})
            # Forward question_card if this was present_question
            _maybe_forward_question_card(
                event, name, send_queue,
                wizard_state=wizard_state,
            )
            # Forward download_ready if this was generate_agent
            _maybe_forward_download_ready(
                event, name, send_queue,
                send_queue.put_nowait, session_id=session_id,
                wizard_state=wizard_state,
            )

        elif etype == SessionEventType.SESSION_ERROR:
            err = getattr(event.data, "message", None) or str(event.data)
            # Flag transient LLM API errors for retry
            if "finish_reason" in err and _retry < MAX_RETRIES:
                logger.warning(
                    "Transient LLM error (will retry, attempt %d/%d): %s",
                    _retry + 1, MAX_RETRIES, err,
                )
                transient_error.append(err)
            else:
                send_queue.put_nowait({"type": "error", "text": err})
            idle_event.set()

        elif etype == SessionEventType.SESSION_IDLE:
            send_queue.put_nowait({"type": "done"})
            idle_event.set()

    unsub = session.on(_handler)
    try:
        await session.send({"prompt": user_text})
        await idle_event.wait()
    finally:
        unsub()

    # Retry on transient errors
    if transient_error and _retry < MAX_RETRIES:
        send_queue.put_nowait({
            "type": "status", "text": "Retrying\u2026",
        })
        await asyncio.sleep(1)
        await stream_response(
            session, user_text, send_queue,
            session_id=session_id, agent=agent,
            _retry=_retry + 1,
        )


def _extract_tool_result_text(event) -> Optional[str]:
    """Extract the raw text content from a TOOL_EXECUTION_COMPLETE event.

    The Copilot SDK wraps tool results in different structures depending
    on version.  This helper tries several extraction strategies:

    1. ``event.data.result.content``  (``Result`` dataclass)
    2. ``event.data.result["content"]`` (dict-style ``Result``)
    3. ``event.data.result["textResultForLlm"]``  (raw ``ToolResult`` dict)
    4. ``str(event.data.result)`` if it looks like JSON
    """
    data = getattr(event, "data", None)
    if data is None:
        return None

    result_obj = getattr(data, "result", None)
    if result_obj is None:
        # Some SDK versions surface the result as a plain data attribute
        result_obj = data.get("result") if isinstance(data, dict) else None
    if result_obj is None:
        return None

    # Strategy 1: Result dataclass .content
    raw = getattr(result_obj, "content", None)
    if raw and isinstance(raw, str):
        return raw

    # Strategy 2: dict-style access
    if isinstance(result_obj, dict):
        raw = result_obj.get("content") or result_obj.get("textResultForLlm")
        if raw and isinstance(raw, str):
            return raw

    # Strategy 3: result is a plain string
    if isinstance(result_obj, str):
        return result_obj

    # Strategy 4: stringify and check it looks like JSON
    try:
        s = str(result_obj)
        if s.startswith("{"):
            return s
    except Exception:
        pass

    logger.debug(
        "Could not extract tool result text. result type=%s, repr=%.300s",
        type(result_obj).__name__, repr(result_obj),
    )
    return None


def _maybe_forward_question_card(
    event, tool_name: str,
    send_queue: asyncio.Queue,
    *,
    wizard_state: Any = None,
) -> None:
    """When present_question completes, forward the question card to the client.

    Uses the wizard state's ``pending_question`` as the primary source,
    since the Copilot SDK ``TOOL_EXECUTION_COMPLETE`` event often does
    not include tool result data or even the correct tool name.

    Checks both the tool name AND wizard_state.pending_question, so
    even if the SDK gives tool_name=None we still forward the card.
    """
    # Check if this looks like a present_question completion.
    # The SDK sometimes drops the tool name, so also check wizard_state.
    has_pending = (
        wizard_state is not None
        and getattr(wizard_state, "pending_question", None) is not None
    )
    is_present_question = (tool_name == "present_question")

    if not is_present_question and not has_pending:
        return

    logger.info(
        "[question_card] Triggered — tool_name=%r, "
        "is_present_question=%s, has_pending=%s",
        tool_name, is_present_question, has_pending,
    )

    payload = None

    # Primary: use wizard_state.pending_question (always set by the tool)
    if wizard_state is not None:
        pending = getattr(wizard_state, "pending_question", None)
        if pending is not None:
            logger.info(
                "[question_card] Using wizard_state.pending_question: "
                "q=%r, options=%r, freetext=%s",
                getattr(pending, "question", "")[:80],
                getattr(pending, "options", []),
                getattr(pending, "allow_freetext", False),
            )
            payload = {
                "question": getattr(pending, "question", ""),
                "options": getattr(pending, "options", []),
                "allow_freetext": getattr(pending, "allow_freetext", False),
                "max_length": getattr(pending, "max_length", 100),
                "allow_multiple": getattr(pending, "allow_multiple", False),
            }
        else:
            logger.warning(
                "[question_card] wizard_state exists but "
                "pending_question is None"
            )
    else:
        logger.warning("[question_card] No wizard_state available")

    # Fallback: try extracting from the event data
    if payload is None:
        raw = _extract_tool_result_text(event)
        logger.info(
            "[question_card] Fallback: event result text=%s",
            repr(raw)[:200] if raw else "NONE",
        )
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and parsed.get("__type__") == "question_card":
                    payload = {
                        "question": parsed.get("question", ""),
                        "options": parsed.get("options", []),
                        "allow_freetext": parsed.get("allow_freetext", False),
                        "max_length": parsed.get("max_length", 100),
                        "allow_multiple": parsed.get("allow_multiple", False),
                    }
                    logger.info(
                        "[question_card] Fallback succeeded from event"
                    )
                else:
                    logger.warning(
                        "[question_card] Fallback: parsed JSON but "
                        "no __type__=question_card: keys=%s",
                        list(parsed.keys()) if isinstance(parsed, dict) else type(parsed),
                    )
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning(
                    "[question_card] Fallback: JSON parse failed: %s",
                    exc,
                )

    if payload is None:
        logger.error(
            "[question_card] FAILED — could not build question card. "
            "wizard_state=%s, event.data attrs=%s, "
            "event.data.result=%s",
            "available" if wizard_state else "N/A",
            [a for a in dir(getattr(event, "data", None))
             if not a.startswith("_")][:20]
            if getattr(event, "data", None) else "N/A",
            repr(getattr(
                getattr(event, "data", None), "result", "N/A"
            ))[:200],
        )
        return

    logger.info(
        "[question_card] SUCCESS — Forwarding to client: q=%r, "
        "options=%r",
        payload.get("question", "")[:80],
        payload.get("options", []),
    )
    send_queue.put_nowait({
        "type": "question_card",
        **payload,
    })
    # Clear pending_question so the card is never sent twice.
    if wizard_state is not None:
        wizard_state.pending_question = None


def _maybe_forward_download_ready(
    event, tool_name: str,
    send_queue: asyncio.Queue, enqueue_fn,
    session_id: str = "",
    *,
    wizard_state: Any = None,
):
    """When generate_agent completes, send a download_ready event."""
    has_gen_result = (
        wizard_state is not None
        and getattr(wizard_state, "last_generate_result", None) is not None
    )
    if tool_name != "generate_agent" and not has_gen_result:
        return

    result = None

    # Primary: use wizard_state.last_generate_result
    if wizard_state is not None:
        result = getattr(wizard_state, "last_generate_result", None)

    # Fallback: try extracting from event data
    if result is None:
        raw = _extract_tool_result_text(event)
        if raw:
            try:
                result = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                pass

    if not isinstance(result, dict):
        return
    if result.get("status") != "generated":
        return
    # The download URL uses the session_id from the WebSocket
    # which matches _session_output_dirs. The project_dir is inside
    # the session's output dir.
    enqueue_fn({
        "type": "download_ready",
        "project_name": Path(
            result.get("project_dir", "project")
        ).name,
        "output_mode": result.get("output_mode", ""),
        "files": result.get("files", []),
        "instructions": result.get("instructions", {}),
        "download_url": (
            f"/api/download-project/{session_id}"
            if session_id else ""
        ),
    })


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

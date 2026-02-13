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
    app = cors(app, allow_origin="*")
    app.ws_sessions: dict = {}  # type: ignore[attr-defined]
    _session_agents: dict = {}  # ws_id -> agent instance
    _session_output_dirs: dict = {}  # ws_id -> output_dir Path
    # Track which sessions use the public factory
    _public_sessions: Set[str] = set()

    # ── Register wizard blueprint ─────────────────────────────────
    try:
        from sciagent.wizard.web import wizard_bp
        app.register_blueprint(wizard_bp)
    except ImportError:
        pass  # wizard dependencies not installed

    # ── Register public wizard blueprint ──────────────────────────
    if public_agent_factory is not None:
        try:
            from sciagent.wizard.public import public_bp
            app.register_blueprint(public_bp)
        except ImportError:
            pass

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
    # ── Serve files from session output directories ──────────────────
    @app.route("/api/session-files/<session_id>/<path:filename>")
    async def session_files(session_id: str, filename: str):
        """Serve files (e.g. saved PNGs) from a session's output dir."""
        out_dir = _session_output_dirs.get(session_id)
        if not out_dir or not out_dir.exists():
            return jsonify({"error": "Unknown session"}), 404
        # Search output dir and immediate subdirs for the file
        target = out_dir / filename
        if not target.exists():
            # Check subdirectories (e.g. scripts/)
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
        from quart import Response
        return Response(
            buf.getvalue(),
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
        # Block the normal chat endpoint when running in public-only mode
        if public_agent_factory is not None:
            await websocket.accept()
            await websocket.send(json.dumps({
                "type": "error",
                "text": "This instance is running in public mode. Please use /public/ instead.",
            }))
            return
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
            """Consume queued figures -- file watcher is primary display path."""
            while True:
                await asyncio.sleep(0.3)
                # Drain the queue so it doesn't grow unbounded, but
                # don't send over WS — the PNG file watcher handles display.
                _ = get_figures(ws_id)

        async def _watch_png_files():
            """Watch the output directory for new PNG files and push them."""
            known_pngs: Set[Path] = set()
            fig_counter = 1000  # offset to avoid collisions with queue figs
            while True:
                await asyncio.sleep(0.5)
                try:
                    if not output_dir.exists():
                        continue
                    current_pngs = set(output_dir.rglob("*.png"))
                    new_pngs = current_pngs - known_pngs
                    for png_path in sorted(new_pngs):
                        try:
                            img_bytes = png_path.read_bytes()
                            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                            await websocket.send(json.dumps({
                                "type": "figure",
                                "data": img_b64,
                                "figure_number": fig_counter,
                                "filename": png_path.name,
                            }))
                            fig_counter += 1
                            logger.debug("Sent saved PNG %s for session %s", png_path.name, ws_id)
                        except Exception:
                            break
                    known_pngs = current_pngs
                except Exception as e:
                    logger.debug("PNG watcher error: %s", e)

        drain_task = asyncio.ensure_future(_drain_queue())
        figure_drain_task = asyncio.ensure_future(_drain_figure_queue())
        png_watch_task = asyncio.ensure_future(_watch_png_files())

        try:
            from sciagent.tools.code_tools import set_output_dir

            agent = agent_factory(output_dir=output_dir)
            _session_agents[ws_id] = agent
            set_output_dir(output_dir)

            # Detect guided mode (public wizard)
            is_guided = getattr(agent, '_guided_mode', False)
            kickoff_received = False

            send_queue.put_nowait({"type": "status", "text": "Starting agent…"})
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
                    if msg_type == "question_response":
                        # Validate the response against the pending question
                        answer = msg.get("answer", "").strip()
                        wizard_state = getattr(agent, '_wizard_state', None)
                        pending = wizard_state.pending_question if wizard_state else None

                        if pending:
                            # Validate option-based responses
                            if not pending.allow_freetext and pending.options:
                                if pending.allow_multiple:
                                    # answer may be comma-separated
                                    answers = [a.strip() for a in answer.split(",")]
                                    valid = all(a in pending.options for a in answers)
                                else:
                                    valid = answer in pending.options
                                if not valid:
                                    send_queue.put_nowait({
                                        "type": "error",
                                        "text": "Please select one of the provided options.",
                                    })
                                    continue
                            # Validate freetext length
                            if pending.allow_freetext and len(answer) > pending.max_length:
                                send_queue.put_nowait({
                                    "type": "error",
                                    "text": f"Response too long (max {pending.max_length} characters).",
                                })
                                continue
                            # Clear pending question
                            wizard_state.pending_question = None

                        user_text = answer
                    elif not kickoff_received:
                        # Allow the initial kickoff message
                        user_text = msg.get("text", "").strip()
                        if user_text:
                            kickoff_received = True
                    else:
                        # Reject freeform chat in guided mode
                        send_queue.put_nowait({
                            "type": "error",
                            "text": "Please use the provided options to respond.",
                        })
                        continue
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
                    await _stream_response(session, user_text, output_dir, send_queue)
                except Exception as send_err:
                    if "Session not found" in str(send_err):
                        logger.warning("Session expired, attempting to resume…")
                        send_queue.put_nowait({"type": "status", "text": "Session expired — reconnecting…"})
                        try:
                            session = await agent.resume_session(ws_id)
                            logger.info("Resumed session %s successfully", ws_id)
                        except Exception:
                            logger.warning("Resume failed for %s, creating new session", ws_id)
                            session = await agent.create_session(session_id=ws_id)
                        await _stream_response(session, user_text, output_dir, send_queue)
                    else:
                        raise
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
            png_watch_task.cancel()
            # Destroy the session to persist data on disk before stopping
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

    # ── Public WebSocket chat (guided mode) ───────────────────────
    if public_agent_factory is not None:
        @app.websocket("/ws/public-chat")
        async def ws_public_chat():
            """WebSocket for public guided-mode sessions.

            Uses the public_agent_factory which creates agents with
            guided_mode=True, so freeform chat is blocked server-side.
            """
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

            drain_task = asyncio.ensure_future(_drain_queue())

            try:
                agent = public_agent_factory(output_dir=output_dir)
                _session_agents[ws_id] = agent

                send_queue.put_nowait({"type": "status", "text": "Starting agent…"})
                await agent.start()

                session = await agent.create_session(session_id=ws_id)
                send_queue.put_nowait({
                    "type": "connected",
                    "session_id": ws_id,
                    "text": "SciAgent Builder ready!",
                })

                kickoff_received = False

                while True:
                    raw = await websocket.receive()
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        msg = {"text": raw}

                    msg_type = msg.get("type", "chat")

                    # ── Guided-mode enforcement ──────────────────
                    if msg_type == "question_response":
                        answer = msg.get("answer", "").strip()
                        wizard_state = getattr(agent, '_wizard_state', None)
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
                                    continue
                            if pending.allow_freetext and len(answer) > pending.max_length:
                                send_queue.put_nowait({
                                    "type": "error",
                                    "text": f"Response too long (max {pending.max_length} characters).",
                                })
                                continue
                            wizard_state.pending_question = None

                        user_text = answer
                    elif not kickoff_received:
                        user_text = msg.get("text", "").strip()
                        if user_text:
                            kickoff_received = True
                    else:
                        send_queue.put_nowait({
                            "type": "error",
                            "text": "Please use the provided options to respond.",
                        })
                        continue

                    if not user_text:
                        continue

                    set_current_session(ws_id)
                    try:
                        await _stream_response(session, user_text, output_dir, send_queue, session_id=ws_id)
                    except Exception as send_err:
                        if "Session not found" in str(send_err):
                            send_queue.put_nowait({"type": "status", "text": "Session expired \u2014 reconnecting\u2026"})
                            try:
                                session = await agent.resume_session(ws_id)
                            except Exception:
                                session = await agent.create_session(session_id=ws_id)
                            await _stream_response(session, user_text, output_dir, send_queue, session_id=ws_id)
                        else:
                            raise
                    set_current_session(None)

            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.exception("Public WebSocket error")
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

    return app


# ── Streaming helper ────────────────────────────────────────────────────

async def _stream_response(
    session, prompt: str, output_dir: Path,
    send_queue: asyncio.Queue, timeout: float = 600,
    session_id: str = "",
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
            # Figures are displayed via the PNG file watcher; skip inline push.
            if not response_text_parts:
                content = _extract_content(event)
                if content:
                    _enqueue({"type": "text_delta", "text": content})

        elif etype == SessionEventType.TOOL_EXECUTION_START:
            name = getattr(event.data, "tool_name", "tool")
            _enqueue({"type": "tool_start", "name": name})

        elif etype == SessionEventType.TOOL_EXECUTION_COMPLETE:
            name = getattr(event.data, "tool_name", "tool")
            # Check for question_card payload from present_question tool
            _maybe_forward_question_card(event, _enqueue)
            # Check for generate_agent completion — send download link
            _maybe_forward_download_ready(
                event, name, send_queue, _enqueue,
                session_id=session_id,
            )
            _enqueue({"type": "tool_complete", "name": name})
            # Figures are displayed via the PNG file watcher; skip inline push.

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


def _maybe_forward_question_card(event, enqueue_fn):
    """Detect a present_question tool result and forward as question_card."""
    raw = None
    if hasattr(event, "data"):
        # SDK wraps result in a Result dataclass with .content str
        result_obj = getattr(event.data, "result", None)
        if result_obj is not None:
            raw = getattr(result_obj, "content", None) or str(result_obj)
        # Fallback: try other attribute names
        if raw is None:
            for attr in ("tool_result", "output", "content"):
                raw = getattr(event.data, attr, None)
                if raw is not None:
                    break
    if raw is None:
        return
    if isinstance(raw, str):
        try:
            result = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return
    elif isinstance(raw, dict):
        result = raw
    else:
        return
    if not isinstance(result, dict):
        return
    if result.get("__type__") != "question_card":
        return
    enqueue_fn({
        "type": "question_card",
        "question": result.get("question", ""),
        "options": result.get("options", []),
        "allow_freetext": result.get("allow_freetext", False),
        "max_length": result.get("max_length", 100),
        "allow_multiple": result.get("allow_multiple", False),
    })


def _maybe_forward_download_ready(
    event, tool_name: str,
    send_queue: asyncio.Queue, enqueue_fn,
    session_id: str = "",
):
    """When generate_agent completes, send a download_ready event."""
    if tool_name != "generate_agent":
        return
    raw = None
    if hasattr(event, "data"):
        result_obj = getattr(event.data, "result", None)
        if result_obj is not None:
            raw = getattr(result_obj, "content", None)
    if not raw:
        return
    try:
        result = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return
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

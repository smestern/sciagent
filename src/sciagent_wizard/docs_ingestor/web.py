"""
Docs ingestor web blueprint — standalone Quart app with WebSocket chat.

Provides a simple form to enter a package name, kicks off deep crawling,
and streams the LLM-based API extraction process to the browser.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from quart import (
    Blueprint,
    Quart,
    jsonify,
    request,
    send_from_directory,
    websocket,
    Response,
)
from quart_cors import cors

from .agent import create_ingestor
from .crawler import crawl_package

logger = logging.getLogger(__name__)

_PKG_DIR = Path(__file__).resolve().parent

ingestor_bp = Blueprint(
    "ingestor",
    __name__,
    static_folder=str(_PKG_DIR / "static"),
    template_folder=str(_PKG_DIR / "templates_html"),
    url_prefix="/ingestor",
)

# ── In-memory result store (session_id → markdown) ─────────────────────
_results: dict = {}


# ── Routes ──────────────────────────────────────────────────────────────


@ingestor_bp.route("/")
async def ingestor_index():
    """Serve the ingestor form page."""
    return await send_from_directory(ingestor_bp.template_folder, "ingestor.html")


@ingestor_bp.route("/api/start", methods=["POST"])
async def ingestor_start():
    """Accept a package name and return a session ID.

    The frontend uses the session_id to open a WebSocket at
    ``/ingestor/ws/ingest``.
    """
    data = await request.get_json(silent=True) or {}
    package_name = data.get("package_name", "").strip()
    github_url = data.get("github_url", "").strip() or None

    if not package_name:
        return jsonify({"error": "package_name is required"}), 400

    session_id = str(uuid.uuid4())
    return jsonify({
        "session_id": session_id,
        "package_name": package_name,
        "github_url": github_url,
    })


@ingestor_bp.route("/api/result/<session_id>")
async def ingestor_result(session_id: str):
    """Download the completed library_api.md for a session."""
    md = _results.get(session_id)
    if not md:
        return jsonify({"error": "No result for this session"}), 404

    return Response(
        md,
        mimetype="text/markdown",
        headers={
            "Content-Disposition": (
                'attachment; filename="library_api.md"'
            )
        },
    )


@ingestor_bp.route("/static/<path:filename>")
async def ingestor_static(filename):
    """Serve ingestor-specific static assets."""
    return await send_from_directory(ingestor_bp.static_folder, filename)


# ── WebSocket ───────────────────────────────────────────────────────────


@ingestor_bp.websocket("/ws/ingest")
async def ws_ingest():
    """WebSocket endpoint for streaming the ingestion process.

    Uses a queue-based drain pattern (same as sciagent's main web app)
    so that WebSocket sends always happen in the correct coroutine
    context rather than from inside Copilot SDK event callbacks.
    """
    agent = None
    session = None
    session_id = ""
    send_queue: asyncio.Queue = asyncio.Queue()
    background_tasks: list = []

    # ── Queue drain loop — sends queued messages over WebSocket ──
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

    try:
        # Wait for the start message with package info
        raw = await websocket.receive()
        msg = json.loads(raw)
        package_name = msg.get("package_name", "").strip()
        github_url = msg.get("github_url", "").strip() or None
        session_id = msg.get("session_id", str(uuid.uuid4()))

        if not package_name:
            send_queue.put_nowait({
                "type": "error",
                "text": "No package name provided.",
            })
            return

        # Phase 1: Crawling
        send_queue.put_nowait({
            "type": "status",
            "text": f"Crawling documentation for {package_name}...",
        })

        try:
            metadata, pages = await crawl_package(
                package_name, github_url,
            )
        except Exception as exc:
            send_queue.put_nowait({
                "type": "error",
                "text": f"Crawling failed: {exc}",
            })
            return

        total_chars = sum(p.char_count for p in pages)
        send_queue.put_nowait({
            "type": "crawl_complete",
            "pages": len(pages),
            "total_chars": total_chars,
            "page_titles": [p.title for p in pages],
        })

        if not pages:
            send_queue.put_nowait({
                "type": "error",
                "text": (
                    "No documentation pages found. "
                    "Try providing a GitHub URL."
                ),
            })
            return

        # Phase 2: LLM extraction
        send_queue.put_nowait({
            "type": "status",
            "text": "Analyzing documentation with LLM...",
        })

        agent = create_ingestor(package_name)
        state = agent.ingestor_state
        state.pip_name = metadata.get("pip_name", package_name)
        state.source_url = metadata.get(
            "repository_url", "",
        )
        state.docs_url = metadata.get("docs_url", "")
        state.pypi_metadata = metadata
        state.scraped_pages = pages

        await agent.start()
        session = await agent.create_session(
            session_id=session_id,
        )

        # Send kickoff message
        kickoff = (
            f"I have scraped {len(pages)} documentation pages "
            f"for **{package_name}** "
            f"({total_chars} chars total). "
            f"Please read through them and extract the API "
            f"reference into the four required sections:\n\n"
            f"1. Core Classes (submit_core_classes)\n"
            f"2. Key Functions (submit_key_functions)\n"
            f"3. Common Pitfalls (submit_pitfalls)\n"
            f"4. Quick-Start Recipes (submit_recipes)\n\n"
            f"Submit each section, then call finalize."
        )

        # Stream events via the queue
        from copilot.generated.session_events import (
            SessionEventType,
        )

        idle_event = asyncio.Event()

        def _handler(event):
            etype = event.type

            if etype == SessionEventType.ASSISTANT_MESSAGE_DELTA:
                delta = (
                    getattr(event.data, "delta_content", None)
                    or ""
                )
                if delta:
                    send_queue.put_nowait({
                        "type": "text_delta",
                        "text": delta,
                    })

            elif etype == SessionEventType.TOOL_EXECUTION_START:
                name = (
                    getattr(event.data, "tool_name", None)
                    or "tool"
                )
                send_queue.put_nowait({
                    "type": "tool_start",
                    "name": name,
                })

            elif etype == SessionEventType.TOOL_EXECUTION_COMPLETE:
                name = (
                    getattr(event.data, "tool_name", None)
                    or "tool"
                )
                send_queue.put_nowait({
                    "type": "tool_complete",
                    "name": name,
                    "sections_filled": state.sections_filled,
                })

            elif etype == SessionEventType.SESSION_ERROR:
                err = (
                    getattr(event.data, "message", None)
                    or str(event.data)
                )
                logger.error("Ingestor session error: %s", err)
                send_queue.put_nowait({
                    "type": "error",
                    "text": err,
                })
                idle_event.set()

            elif etype == SessionEventType.SESSION_IDLE:
                idle_event.set()

        unsub = session.on(_handler)
        try:
            await session.send({"prompt": kickoff})
            await idle_event.wait()
        finally:
            unsub()

        # ── Deliver result ───────────────────────────────────
        if not state.final_markdown and state.sections_filled:
            # Agent submitted sections but didn't call finalize
            logger.warning(
                "Agent didn't call finalize — assembling "
                "manually (sections: %s)",
                state.sections_filled,
            )
            from . import tools as ingestor_tools
            ingestor_tools.tool_finalize(state)

        if state.final_markdown:
            _results[session_id] = state.final_markdown
            send_queue.put_nowait({
                "type": "result",
                "markdown": state.final_markdown,
                "download_url": (
                    f"/ingestor/api/result/{session_id}"
                ),
            })
        else:
            send_queue.put_nowait({
                "type": "error",
                "text": (
                    "LLM did not produce a complete result. "
                    f"Sections filled: {state.sections_filled}"
                ),
            })

        send_queue.put_nowait({"type": "done"})

    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.exception("Ingestor WebSocket error")
        try:
            send_queue.put_nowait({
                "type": "error",
                "text": str(exc),
            })
        except Exception:
            pass
    finally:
        # Signal the drain loop to stop
        send_queue.put_nowait(None)
        # Give the drain loop a moment to flush
        await asyncio.sleep(0.1)
        for task in background_tasks:
            task.cancel()
        if session and agent:
            try:
                await agent.destroy_session(session_id)
            except Exception:
                pass
        if agent:
            try:
                await agent.stop()
            except Exception:
                pass


# ── Standalone app factory ──────────────────────────────────────────────


def create_ingestor_app() -> Quart:
    """Create a standalone Quart app for the docs ingestor."""
    app = Quart(
        __name__,
        static_folder=str(_PKG_DIR / "static"),
        template_folder=str(_PKG_DIR / "templates_html"),
    )
    app = cors(app, allow_origin="*")
    app.register_blueprint(ingestor_bp)

    @app.route("/")
    async def root():
        from quart import redirect
        return redirect("/ingestor/")

    return app

"""
ScientificCLI — Rich terminal REPL for scientific agents.

Subclass and override ``banner()``, ``get_example_prompts()``,
and ``get_slash_commands()`` for domain customisation.
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from sciagent.config import AgentConfig

console = Console()

# ── Slash-command type ──────────────────────────────────────────────────
SlashEntry = Tuple[str, str, Callable]  # (name, description, handler_coro)


class ScientificCLI:
    """Generic interactive CLI for a scientific agent.

    Args:
        agent_factory: ``(output_dir=...) -> BaseScientificAgent``
        config: Domain configuration (name, colours, prompts, etc.).
        output_dir: Override output directory (defaults to CWD/output).
    """

    def __init__(
        self,
        agent_factory: Callable,
        config: Optional[AgentConfig] = None,
        output_dir: Optional[Path] = None,
    ):
        self.agent_factory = agent_factory
        self.config = config or AgentConfig()
        self.output_dir = output_dir or Path.cwd() / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._agent = None
        self._session = None
        self._history_path = Path(tempfile.gettempdir()) / f"{self.config.name}_history.txt"
        self._figure_counter = 0

    # ── Overridable ─────────────────────────────────────────────────

    def banner(self) -> str:
        """Return the startup banner text."""
        return (
            f"[bold]{self.config.logo_emoji} {self.config.display_name}[/bold]\n"
            f"[dim]{self.config.description}[/dim]\n\n"
            "Type your question or /help for commands."
        )

    def get_example_prompts(self) -> list[str]:
        """Return example prompts shown in /help."""
        return [c.prompt for c in self.config.suggestion_chips]

    def get_slash_commands(self) -> list[SlashEntry]:
        """Extra domain slash commands — return list of (name, desc, handler)."""
        return []

    # ── Core commands ───────────────────────────────────────────────

    async def _cmd_help(self):
        table = Table(title="Commands", show_header=True)
        table.add_column("Command", style="bold cyan")
        table.add_column("Description")
        for name, desc, _ in self._all_commands():
            table.add_row(f"/{name}", desc)
        console.print(table)
        examples = self.get_example_prompts()
        if examples:
            console.print("\n[bold]Example prompts:[/bold]")
            for ex in examples:
                console.print(f"  [dim]•[/dim] {ex}")

    async def _cmd_save(self):
        console.print(f"[green]Output directory:[/green] {self.output_dir}")

    async def _cmd_clear(self):
        if self._agent:
            self._session = await self._agent.create_session()
            console.print("[yellow]Session cleared.[/yellow]")
            self._figure_counter = 0

    async def _cmd_export(self):
        """Ask the agent to produce a reproducible script from the session."""
        from sciagent.tools.session_log import get_session_log
        log = get_session_log()
        if log is None or not log.has_successful_steps:
            console.print("[yellow]No analysis steps recorded yet — nothing to export.[/yellow]")
            return
        console.print("[dim]Asking agent to compose a reproducible script…[/dim]")
        await self._stream_and_print(
            "Please review the session log with get_session_log and produce a clean, "
            "standalone reproducible Python script for the analysis we just performed. "
            "The script should include argparse with --input-file and --output-dir, "
            "all necessary imports, and only the working analysis steps. "
            "Save it using the save_reproducible_script tool."
        )

    async def _cmd_quit(self):
        raise KeyboardInterrupt

    def _all_commands(self) -> list[SlashEntry]:
        base = [
            ("help", "Show this help", self._cmd_help),
            ("save", "Show output directory", self._cmd_save),
            ("export", "Generate a reproducible script from this session", self._cmd_export),
            ("clear", "Reset chat session", self._cmd_clear),
            ("quit", "Exit the CLI", self._cmd_quit),
        ]
        base.extend(self.get_slash_commands())
        return base

    # ── Streaming handler ───────────────────────────────────────────

    async def _stream_and_print(self, prompt: str):
        """Send *prompt* to the agent session and stream output to console."""
        from copilot.generated.session_events import SessionEventType

        idle_event = asyncio.Event()
        text_parts: list[str] = []
        thinking_parts: list[str] = []

        def _flush_thinking():
            """Print and clear any buffered thinking/reasoning text."""
            if thinking_parts:
                snippet = "".join(thinking_parts)
                console.print(Panel(
                    snippet[:500] + ("…" if len(snippet) > 500 else ""),
                    title="💭 Thinking",
                    style="dim",
                    expand=False,
                ))
                thinking_parts.clear()

        def _flush_text() -> bool:
            """Print and clear any buffered assistant text. Returns True if anything was printed."""
            chunk = "".join(text_parts).strip()
            text_parts.clear()
            if chunk:
                console.print()
                console.print(Markdown(chunk))
                console.print()
                return True
            return False

        def _handler(event):
            etype = event.type

            if etype == SessionEventType.ASSISTANT_REASONING_DELTA:
                delta = getattr(event.data, "delta_content", None) or ""
                if delta:
                    thinking_parts.append(delta)

            elif etype == SessionEventType.ASSISTANT_REASONING:
                text = getattr(event.data, "reasoning_text", None) or ""
                if text:
                    thinking_parts.append(text)

            elif etype == SessionEventType.ASSISTANT_MESSAGE_DELTA:
                delta = getattr(event.data, "delta_content", None) or ""
                if delta:
                    text_parts.append(delta)

            elif etype == SessionEventType.ASSISTANT_MESSAGE:
                # Flush thinking first, then accumulated text before tool calls
                _flush_thinking()
                flushed = _flush_text()
                self._print_figures_from_event(event)
                # Only extract full content if no deltas were accumulated
                if not flushed:
                    content = self._extract_content(event)
                    if content and content.strip():
                        console.print()
                        console.print(Markdown(content.strip()))
                        console.print()

            elif etype == SessionEventType.TOOL_EXECUTION_START:
                # Flush any buffered text so it appears before the tool message
                _flush_thinking()
                _flush_text()
                name = getattr(event.data, "tool_name", "tool")
                console.print(f"  [dim]⚙ Running {name}…[/dim]")

            elif etype == SessionEventType.TOOL_EXECUTION_COMPLETE:
                name = getattr(event.data, "tool_name", "tool")
                console.print(f"  [dim]✓ {name} done[/dim]")
                self._print_figures_from_tool_event(event)

            elif etype == SessionEventType.SESSION_ERROR:
                err = getattr(event.data, "message", str(event.data))
                console.print(f"[red]Error: {err}[/red]")
                idle_event.set()

            elif etype == SessionEventType.SESSION_IDLE:
                idle_event.set()

        unsub = self._session.on(_handler)
        try:
            await self._session.send({"prompt": prompt})
            await idle_event.wait()
        finally:
            unsub()

        # Flush any remaining text that arrived after the last tool call
        _flush_thinking()
        _flush_text()

    def _print_figures_from_event(self, event):
        tool_results = getattr(event, "tool_results", None)
        if not tool_results and hasattr(event, "data"):
            tool_results = getattr(event.data, "tool_results", None)
        if not tool_results:
            return
        items = tool_results if isinstance(tool_results, list) else [tool_results]
        for tr in items:
            if isinstance(tr, dict):
                for fig in tr.get("figures", []):
                    self._save_and_show_figure(fig)

    def _print_figures_from_tool_event(self, event):
        result = None
        if hasattr(event, "data"):
            for attr in ("result", "tool_result", "output", "content"):
                result = getattr(event.data, attr, None)
                if result is not None:
                    break
        if isinstance(result, str):
            try:
                import json
                result = json.loads(result)
            except Exception:
                pass
        if isinstance(result, dict):
            for fig in result.get("figures", []):
                self._save_and_show_figure(fig)

    def _save_and_show_figure(self, fig: dict):
        if not isinstance(fig, dict) or "image_base64" not in fig:
            return
        self._figure_counter += 1
        fig_path = self.output_dir / "figures" / f"figure_{self._figure_counter}.png"
        fig_path.parent.mkdir(parents=True, exist_ok=True)
        raw = base64.b64decode(fig["image_base64"])
        fig_path.write_bytes(raw)
        console.print(f"  [green]📊 Figure {self._figure_counter} saved → {fig_path}[/green]")
        # Try to open on supported platforms
        self._open_figure(fig_path)

    @staticmethod
    def _open_figure(path: Path):
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    @staticmethod
    def _extract_content(event) -> Optional[str]:
        if hasattr(event, "data") and hasattr(event.data, "content"):
            return event.data.content
        if isinstance(event, dict):
            return event.get("content") or event.get("message")
        return None

    # ── REPL ────────────────────────────────────────────────────────

    async def run(self):
        """Launch the interactive REPL."""
        console.print(Panel(self.banner(), expand=False))

        from sciagent.tools.code_tools import set_output_dir
        set_output_dir(self.output_dir)

        self._agent = self.agent_factory(output_dir=self.output_dir)
        console.print("[dim]Starting agent…[/dim]")
        console.print(f"[dim]Working directory: {self.output_dir}[/dim]")
        await self._agent.start()
        self._session = await self._agent.create_session()
        console.print("[green]Ready![/green]\n")

        prompt_session: PromptSession = PromptSession(
            history=FileHistory(str(self._history_path)),
        )

        commands = {c[0]: c[2] for c in self._all_commands()}

        try:
            while True:
                try:
                    user_input = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: prompt_session.prompt(f"{self.config.logo_emoji} > "),
                    )
                except EOFError:
                    break

                text = user_input.strip()
                if not text:
                    continue

                # Slash commands
                if text.startswith("/"):
                    cmd_name = text.split()[0][1:].lower()
                    handler = commands.get(cmd_name)
                    if handler:
                        await handler()
                    else:
                        console.print(f"[red]Unknown command: /{cmd_name}. Type /help.[/red]")
                    continue

                # Regular prompt
                try:
                    await self._stream_and_print(text)
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Goodbye![/yellow]")
        finally:
            # Auto-export reproducible script if analysis was performed
            await self._auto_export_script()
            if self._agent:
                try:
                    await self._agent.stop()
                except Exception:
                    pass

    async def _auto_export_script(self):
        """Prompt the agent to export a reproducible script at session end."""
        try:
            from sciagent.tools.session_log import get_session_log
            log = get_session_log()
            if (
                log is not None
                and log.has_successful_steps
                and not log.script_exported
                and self._session is not None
            ):
                console.print("\n[dim]Generating reproducible script…[/dim]")
                await self._stream_and_print(
                    "Before we end, please review the session log with get_session_log "
                    "and produce a clean, standalone reproducible Python script for "
                    "the analysis performed in this session. Include argparse with "
                    "--input-file and --output-dir, all necessary imports, and only "
                    "the working analysis steps. Save it using save_reproducible_script."
                )
        except Exception as e:
            logger.debug("Auto-export failed: %s", e)


# ── Entry point helper ──────────────────────────────────────────────────

def run_cli(
    agent_factory: Callable,
    config: Optional[AgentConfig] = None,
    output_dir: Optional[Path] = None,
):
    """Convenience wrapper: create a ``ScientificCLI`` and start the REPL."""
    cli = ScientificCLI(agent_factory, config, output_dir)
    asyncio.run(cli.run())

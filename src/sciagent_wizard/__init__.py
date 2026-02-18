"""
sciagent_wizard — Self-assembly wizard for building domain-specific agents.

The wizard lets non-programmer researchers describe their domain, provide
example data, and automatically:

1. Discover relevant scientific packages from peer-reviewed databases
   (PyPI, bio.tools, Papers With Code, PubMed)
2. Rank and de-duplicate candidates across sources
3. Generate a fully functional agent project (config, tools, prompts)
4. Launch the agent immediately — and persist it for reuse

Usage::

    from sciagent_wizard import create_wizard, WIZARD_CONFIG

    # Conversational (wizard is itself an agent)
    wizard = create_wizard()

    # Public / guided mode (no freeform chat)
    wizard = create_wizard(guided_mode=True)

    # Or via CLI
    # sciagent-wizard
    # sciagent-wizard --public
"""

from sciagent_wizard.agent import create_wizard, WIZARD_CONFIG

__all__ = ["create_wizard", "WIZARD_CONFIG", "main", "main_public"]


def main():
    """Entry point for ``sciagent-wizard`` console script."""
    import os
    import sys
    from sciagent_wizard.models import OutputMode

    # Load .env file if present (never overrides existing env vars)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    web = "--cli" not in sys.argv
    public_mode = (
        "--public" in sys.argv
        or os.environ.get("SCIAGENT_PUBLIC_MODE", "0") == "1"
    )
    port = 5000
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    # Parse --output-mode / -m flag
    output_mode = OutputMode.FULLSTACK
    for flag in ("--output-mode", "-m"):
        if flag in sys.argv:
            idx = sys.argv.index(flag)
            if idx + 1 < len(sys.argv):
                try:
                    output_mode = OutputMode(sys.argv[idx + 1])
                except ValueError:
                    print(f"Invalid output mode: {sys.argv[idx + 1]}")
                    print("Valid modes: fullstack, copilot_agent, markdown")
                    sys.exit(1)

    # In public mode, force non-fullstack default
    if public_mode and output_mode == OutputMode.FULLSTACK:
        output_mode = OutputMode.MARKDOWN

    def _factory(**kwargs):
        w = create_wizard(**kwargs)
        w.wizard_state.output_mode = output_mode
        return w

    def _public_factory(**kwargs):
        w = create_wizard(guided_mode=True, **kwargs)
        w.wizard_state.output_mode = output_mode
        return w

    if web:
        from sciagent.web.app import create_app
        from rich.console import Console
        from rich.panel import Panel

        console = Console()

        if public_mode:
            console.print(Panel(
                "[bold]🧙 SciAgent Public Builder[/bold]\n"
                f"[dim]Open http://localhost:{port}/public in your browser[/dim]\n"
                f"[dim]Guided mode • No freeform chat • Rate limited[/dim]",
                expand=False,
            ))
            app = create_app(
                _factory, WIZARD_CONFIG,
                public_agent_factory=_public_factory,
            )
        else:
            console.print(Panel(
                "[bold]\U0001f9d9 SciAgent Self-Assembly Wizard[/bold]\n"
                f"[dim]Open http://localhost:{port}/wizard in your browser[/dim]\n"
                f"[dim]Output mode: {output_mode.value}[/dim]",
                expand=False,
            ))
            app = create_app(_factory, WIZARD_CONFIG)

        app.run(host="0.0.0.0", port=port)
    else:
        from sciagent.cli import run_cli
        run_cli(_factory, WIZARD_CONFIG)


def main_public():
    """Entry point for ``sciagent-public`` console script.

    Convenience wrapper that sets SCIAGENT_PUBLIC_MODE=1 and delegates
    to ``main()``.
    """
    import os
    os.environ["SCIAGENT_PUBLIC_MODE"] = "1"
    main()

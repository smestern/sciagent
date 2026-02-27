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

__all__ = [
    "create_wizard",
    "WIZARD_CONFIG",
    "main",
    "main_public",
    "register_plugin",
]


def register_plugin():
    """Entry point for ``sciagent.plugins`` discovery.

    Returns a :class:`~sciagent.plugins.PluginRegistration` describing
    the wizard's contributions to the core framework (blueprints, CLI
    commands, auth, tools).
    """
    from sciagent.plugins import PluginRegistration

    return PluginRegistration(
        name="wizard",
        register_web=_register_web,
        register_cli=_register_cli,
        get_auth_token=_get_auth_token,
        supported_models=_get_supported_models(),
        tool_providers={
            "ingest_package_docs_sync": _get_ingest_fn,
        },
    )


# ── Plugin callbacks (kept private) ─────────────────────────────────────


def _register_web(app, *, public_agent_factory=None, **_kwargs):
    """Register wizard blueprints and auth on the Quart app."""
    import os

    # OAuth session support (opt-in)
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
        pass

    # Main wizard blueprint
    try:
        from sciagent_wizard.web import wizard_bp
        app.register_blueprint(wizard_bp)
    except ImportError:
        pass

    # Public wizard blueprint + redirect overrides
    if public_agent_factory is not None:
        try:
            from sciagent_wizard.public import public_bp
            app.register_blueprint(public_bp)
        except ImportError:
            pass

        @app.route("/wizard/")
        @app.route("/wizard")
        async def wizard_redirect_to_public():
            from quart import redirect
            return redirect("/public/")

        @app.route("/wizard/api/start", methods=["POST"])
        async def wizard_api_redirect_to_public():
            from quart import redirect
            return redirect("/public/api/start", code=307)

    # Docs ingestor blueprint
    try:
        from sciagent_wizard.docs_ingestor.web import ingestor_bp
        app.register_blueprint(ingestor_bp)
    except ImportError:
        pass


def _register_cli(typer_app):
    """Register the ``wizard`` CLI sub-command on the Typer app."""
    import typer as _typer
    from typing import Optional
    from pathlib import Path

    @typer_app.command()
    def wizard(
        web: bool = _typer.Option(
            True, "--web/--cli", help="Launch in web or CLI mode.",
        ),
        port: int = _typer.Option(
            5000, "--port", "-p", help="Web server port.",
        ),
        output_dir: Optional[Path] = _typer.Option(
            None, "--output-dir", "-o",
            help="Output directory for generated agents.",
        ),
        output_mode: str = _typer.Option(
            "fullstack", "--output-mode", "-m",
            help="Output mode: fullstack, copilot_agent, or markdown.",
        ),
        rigor_level: str = _typer.Option(
            "standard", "--rigor-level", "-r",
            help="Rigor enforcement level: strict, standard, relaxed, or bypass.",
        ),
    ):
        """🧙 Launch the self-assembly wizard to build a domain-specific agent."""
        from sciagent_wizard import create_wizard, WIZARD_CONFIG
        from sciagent_wizard.models import OutputMode

        try:
            mode = OutputMode(output_mode)
        except ValueError:
            from rich.console import Console
            Console().print(f"[red]Invalid output mode: {output_mode}[/red]")
            Console().print("[dim]Valid modes: fullstack, copilot_agent, markdown[/dim]")
            raise _typer.Exit(1)

        from sciagent.guardrails.scanner import RigorLevel
        _rigor = RigorLevel.from_str(rigor_level)

        def _factory(**kwargs):
            w = create_wizard(**kwargs)
            w.wizard_state.output_mode = mode
            return w

        WIZARD_CONFIG.rigor_level = _rigor.value

        if web:
            from sciagent.web.app import create_app
            from rich.console import Console
            from rich.panel import Panel

            Console().print(Panel(
                "[bold]🧙 SciAgent Self-Assembly Wizard[/bold]\n"
                f"[dim]Open http://localhost:{port}/wizard in your browser[/dim]\n"
                f"[dim]Output mode: {mode.value}[/dim]\n"
                f"[dim]Rigor level: {_rigor.value}[/dim]",
                expand=False,
            ))
            app_instance = create_app(_factory, WIZARD_CONFIG)
            app_instance.run(host="0.0.0.0", port=port)
        else:
            from sciagent.cli import run_cli
            run_cli(_factory, WIZARD_CONFIG, output_dir, rigor_level=_rigor.value)


def _get_auth_token():
    """Return the GitHub OAuth token from the current session, if any."""
    try:
        from sciagent_wizard.auth import get_github_token
        return get_github_token()
    except ImportError:
        return None


def _get_supported_models():
    """Return the wizard's SUPPORTED_MODELS as a name→True dict."""
    try:
        from sciagent_wizard.models import SUPPORTED_MODELS
        return {m: True for m in SUPPORTED_MODELS}
    except ImportError:
        return {}


def _get_ingest_fn():
    """Lazy loader for the docs ingestor function."""
    from sciagent_wizard.docs_ingestor import ingest_package_docs_sync
    return ingest_package_docs_sync


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


def create_production_app():
    """Application factory for production ASGI servers (Hypercorn/Uvicorn).

    Returns a configured Quart app without calling ``app.run()``.
    Reads configuration from environment variables:

    * ``SCIAGENT_PUBLIC_MODE`` — set to ``1`` to enable public/guided mode.
    * ``SCIAGENT_OUTPUT_MODE`` — ``markdown``, ``copilot_agent``, or
      ``fullstack`` (defaults to ``markdown`` in public mode).

    Usage with Hypercorn::

        hypercorn "sciagent_wizard:create_production_app()" \
            --bind 0.0.0.0:$PORT
    """
    import os
    from sciagent_wizard.models import OutputMode

    # Load .env file if present
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    public_mode = os.environ.get("SCIAGENT_PUBLIC_MODE", "0") == "1"
    output_mode_str = os.environ.get("SCIAGENT_OUTPUT_MODE", "")
    if output_mode_str:
        try:
            output_mode = OutputMode(output_mode_str)
        except ValueError:
            output_mode = OutputMode.MARKDOWN
    elif public_mode:
        output_mode = OutputMode.MARKDOWN
    else:
        output_mode = OutputMode.FULLSTACK

    # In public mode, force non-fullstack default (match CLI behavior)
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

    from sciagent.web.app import create_app

    if public_mode:
        app = create_app(
            _factory, WIZARD_CONFIG,
            public_agent_factory=_public_factory,
        )
    else:
        app = create_app(_factory, WIZARD_CONFIG)

    return app

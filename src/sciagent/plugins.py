"""
sciagent.plugins — Plugin discovery via setuptools entry points.

Third-party packages (e.g. ``sciagent-wizard``) register themselves under
the ``sciagent.plugins`` entry-point group.  Each entry point resolves to
a callable (no arguments) that returns a :class:`PluginRegistration`
instance (or compatible dict).

Usage in core code::

    from sciagent.plugins import discover_plugins

    for plugin in discover_plugins():
        if plugin.register_web:
            plugin.register_web(app, public_agent_factory=pf)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "sciagent.plugins"


@dataclass
class PluginRegistration:
    """Declares what a plugin contributes to the sciagent framework.

    Attributes
    ----------
    name : str
        Human-readable plugin identifier (populated from entry-point
        name if left empty).
    register_web : callable, optional
        ``(app: Quart, **context) -> None`` — registers blueprints,
        auth middleware, and route overrides on the Quart application.
        Receives ``public_agent_factory`` in *context* when available.
    register_cli : callable, optional
        ``(app: typer.Typer) -> None`` — registers CLI sub-commands
        on the Typer application.
    get_auth_token : callable, optional
        ``() -> Optional[str]`` — returns an auth token for the
        current request context (e.g. OAuth session token).
    supported_models : dict, optional
        Mapping of ``model_id -> metadata`` exposed by the plugin
        for model routing / billing.
    tool_providers : dict
        Mapping of ``tool_name -> callable`` for lazy tool resolution.
        The callable is invoked with no arguments and should return the
        actual tool function (or module-level function) to call.
    """

    name: str = ""
    register_web: Optional[Callable] = None
    register_cli: Optional[Callable] = None
    get_auth_token: Optional[Callable] = None
    supported_models: Optional[Dict[str, Any]] = None
    tool_providers: Dict[str, Callable] = field(default_factory=dict)


# ── Discovery ───────────────────────────────────────────────────────────

_cached_plugins: Optional[List[PluginRegistration]] = None


def discover_plugins(*, reload: bool = False) -> List[PluginRegistration]:
    """Load all installed sciagent plugins.

    Results are cached after the first call.  Pass ``reload=True``
    to force re-discovery (e.g. after installing a new plugin at
    runtime).

    Returns
    -------
    list[PluginRegistration]
        All successfully loaded plugin registrations.
    """
    global _cached_plugins
    if _cached_plugins is not None and not reload:
        return _cached_plugins

    plugins: List[PluginRegistration] = []

    try:
        from importlib.metadata import entry_points as _ep_fn

        try:
            eps = _ep_fn(group=ENTRY_POINT_GROUP)
        except TypeError:
            # Python 3.9 compat: entry_points() doesn't accept group=
            eps = _ep_fn().get(ENTRY_POINT_GROUP, [])  # type: ignore[union-attr]
    except ImportError:
        eps = []

    for ep in eps:
        try:
            factory = ep.load()
            result = factory()
            if isinstance(result, PluginRegistration):
                if not result.name:
                    result.name = ep.name
                plugins.append(result)
            elif isinstance(result, dict):
                plugins.append(PluginRegistration(name=ep.name, **result))
            else:
                logger.warning(
                    "Plugin %r returned unsupported type %s — skipping",
                    ep.name,
                    type(result).__name__,
                )
        except Exception:
            logger.exception("Failed to load plugin %r", ep.name)

    _cached_plugins = plugins
    if plugins:
        logger.info(
            "Discovered %d sciagent plugin(s): %s",
            len(plugins),
            [p.name for p in plugins],
        )
    return plugins


# ── Convenience helpers ─────────────────────────────────────────────────


def get_auth_token() -> Optional[str]:
    """Return the first non-``None`` auth token from installed plugins."""
    for plugin in discover_plugins():
        if plugin.get_auth_token:
            try:
                token = plugin.get_auth_token()
                if token:
                    return token
            except Exception:
                logger.debug(
                    "Plugin %r get_auth_token raised", plugin.name,
                    exc_info=True,
                )
    return None


def get_supported_models() -> Dict[str, Any]:
    """Merge supported-model dicts from all installed plugins."""
    merged: Dict[str, Any] = {}
    for plugin in discover_plugins():
        if plugin.supported_models:
            merged.update(plugin.supported_models)
    return merged


def get_tool_provider(name: str) -> Optional[Callable]:
    """Look up a tool provider by name across all installed plugins."""
    for plugin in discover_plugins():
        provider = plugin.tool_providers.get(name)
        if provider is not None:
            return provider
    return None

"""
sciagent.wizard — Self-assembly wizard for building domain-specific agents.

The wizard lets non-programmer researchers describe their domain, provide
example data, and automatically:

1. Discover relevant scientific packages from peer-reviewed databases
   (PyPI, bio.tools, Papers With Code, SciCrunch, PubMed)
2. Rank and de-duplicate candidates across sources
3. Generate a fully functional agent project (config, tools, prompts)
4. Launch the agent immediately — and persist it for reuse

Usage::

    from sciagent.wizard import create_wizard, WIZARD_CONFIG

    # Conversational (wizard is itself an agent)
    wizard = create_wizard()

    # Or via CLI
    # sciagent wizard
"""

from .wizard_agent import create_wizard, WIZARD_CONFIG

__all__ = ["create_wizard", "WIZARD_CONFIG"]

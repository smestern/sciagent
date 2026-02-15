"""
sciagent.wizard.generator — Generate a complete agent project from wizard state.
"""

from .project import generate_project
from .docs_gen import write_docs
from .copilot_gen import generate_copilot_project
from .markdown_gen import generate_markdown_project
from .template_renderer import (
    render_docs,
    render_template,
    copy_blank_templates,
)

__all__ = [
    "generate_project",
    "write_docs",
    "generate_copilot_project",
    "generate_markdown_project",
    "render_docs",
    "render_template",
    "copy_blank_templates",
]

"""sciagent.web — Browser-based chat UI infrastructure."""

from .figure_queue import (
    register_session,
    unregister_session,
    set_current_session,
    get_current_session,
    get_figures,
    push_figure,
    push_figure_to_current_session,
)

__all__ = [
    "register_session",
    "unregister_session",
    "set_current_session",
    "get_current_session",
    "get_figures",
    "push_figure",
    "push_figure_to_current_session",
]

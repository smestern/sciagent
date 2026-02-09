"""sciagent.prompts — System prompt building blocks."""

from .base_messages import (
    BASE_SCIENTIFIC_PRINCIPLES,
    CODE_EXECUTION_POLICY,
    OUTPUT_DIR_POLICY,
    THINKING_OUT_LOUD_POLICY,
    COMMUNICATION_STYLE_POLICY,
    build_system_message,
)

__all__ = [
    "BASE_SCIENTIFIC_PRINCIPLES",
    "CODE_EXECUTION_POLICY",
    "OUTPUT_DIR_POLICY",
    "THINKING_OUT_LOUD_POLICY",
    "COMMUNICATION_STYLE_POLICY",
    "build_system_message",
]

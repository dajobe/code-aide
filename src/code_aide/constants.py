"""Shared constants and tool configuration for CLI modules.

``TOOLS`` is exposed as a read-only :class:`types.MappingProxyType` view over
``_TOOLS_DATA`` so production code cannot accidentally rebind tool entries.
Tests that need a different fixture should patch ``_TOOLS_DATA`` directly via
``mock.patch.dict`` — mutations to the underlying dict are visible through
the proxy.
"""

import os
import sys
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional

from code_aide.config import load_tools_config


def _use_color() -> bool:
    """Determine whether to emit ANSI color codes.

    Checks (in priority order):
      NO_COLOR          — if set (any value), no color (https://no-color.org/)
      FORCE_COLOR       — if set (any value), force color
      CLICOLOR_FORCE    — if non-empty, force color
      TERM=dumb         — no color
      CLICOLOR=0        — no color
      stdout is not a TTY — no color
    """
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("FORCE_COLOR") is not None:
        return True
    if os.environ.get("CLICOLOR_FORCE", ""):
        return True
    if os.environ.get("TERM") == "dumb":
        return False
    if os.environ.get("CLICOLOR") == "0":
        return False
    return sys.stdout.isatty()


_COLOR_CODES: Dict[str, str] = {
    "RED": "\033[0;31m",
    "GREEN": "\033[0;32m",
    "YELLOW": "\033[1;33m",
    "BLUE": "\033[0;34m",
    "BOLD": "\033[1m",
    "NC": "\033[0m",
}

# Resolved once, on first Colors attribute access, so environment
# variables (NO_COLOR, FORCE_COLOR, ...) set after import still apply.
_color_state: Dict[str, Optional[bool]] = {"enabled": None}


class _ColorsMeta(type):
    """Metaclass giving Colors lazy class-level attributes."""

    def _colors_enabled(cls) -> bool:
        enabled = _color_state["enabled"]
        if enabled is None:
            enabled = _use_color()
            _color_state["enabled"] = enabled
        return enabled

    def __getattr__(cls, name: str) -> str:
        if name in _COLOR_CODES:
            return _COLOR_CODES[name] if cls._colors_enabled() else ""
        raise AttributeError(name)


class Colors(metaclass=_ColorsMeta):
    """ANSI color codes resolved on first attribute access."""


_TOOLS_DATA: Dict[str, Dict[str, Any]] = load_tools_config()
TOOLS: Mapping[str, Dict[str, Any]] = MappingProxyType(_TOOLS_DATA)

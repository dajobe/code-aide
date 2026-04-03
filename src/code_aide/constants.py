"""Shared constants and mutable tool configuration for CLI modules."""

import os
import sys
from typing import Any, Dict

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


class Colors:
    if _use_color():
        RED = "\033[0;31m"
        GREEN = "\033[0;32m"
        YELLOW = "\033[1;33m"
        BLUE = "\033[0;34m"
        BOLD = "\033[1m"
        NC = "\033[0m"
    else:
        RED = ""
        GREEN = ""
        YELLOW = ""
        BLUE = ""
        BOLD = ""
        NC = ""


TOOLS: Dict[str, Dict[str, Any]] = load_tools_config()

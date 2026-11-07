"""Find every copy of a tool's command on PATH.

Only the first copy on PATH runs; later ones are shadowed. Shadowed copies
are easy to miss (for example one npm global install under ``~/.npm-packages``
and another made with Homebrew's npm under ``/opt/homebrew``), so status and
upgrades report them with a removal hint where one is known.
"""

import os
import re
import shlex
from dataclasses import dataclass
from typing import List, Optional

from code_aide.app_bundle import is_app_bundle_tool
from code_aide.constants import TOOLS
from code_aide.detection import detect_install_method_at
from code_aide.detection_types import DetectedInstallInfo
from code_aide.install_types import InstallMethod, parse_install_method


@dataclass(frozen=True)
class CommandCopy:
    """One copy of a command found on PATH."""

    path: str
    real_path: str
    install: DetectedInstallInfo


def find_command_copies(tool_name: str) -> List[CommandCopy]:
    """Return each distinct copy of the tool's command in PATH order.

    Copies that resolve to the same file (for example a symlink in two PATH
    directories) are reported once, at their first PATH position.
    """
    tool_config = TOOLS.get(tool_name)
    if not tool_config or is_app_bundle_tool(tool_config):
        return []
    command = tool_config["command"]

    seen = set()
    copies = []
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        candidate = os.path.join(directory, command)
        if not (os.path.isfile(candidate) and os.access(candidate, os.X_OK)):
            continue
        real_path = os.path.realpath(candidate)
        if real_path in seen:
            continue
        seen.add(real_path)
        copies.append(
            CommandCopy(
                path=candidate,
                real_path=real_path,
                install=detect_install_method_at(tool_config, candidate),
            )
        )
    return copies


def shadowed_copies(tool_name: str) -> List[CommandCopy]:
    """Return the copies of the tool's command hidden behind the first one."""
    return find_command_copies(tool_name)[1:]


def npm_prefix_for(real_path: str) -> Optional[str]:
    """Return the npm global prefix that owns a node_modules path."""
    match = re.match(r"(.+?)/lib/node_modules/", real_path)
    return match.group(1) if match else None


def removal_hint(copy: CommandCopy) -> Optional[str]:
    """Return a shell command that removes this copy, when one is known."""
    method = parse_install_method(copy.install["method"])
    detail = copy.install["detail"]
    if method in (InstallMethod.NPM, InstallMethod.BREW_NPM) and detail:
        prefix = npm_prefix_for(copy.real_path)
        if prefix:
            return f"npm uninstall -g --prefix {shlex.quote(prefix)} {detail}"
        return f"npm uninstall -g {detail}"
    if method == InstallMethod.BREW_FORMULA and detail:
        return f"brew uninstall {detail}"
    if method == InstallMethod.BREW_CASK and detail:
        return f"brew uninstall --cask {detail}"
    return None

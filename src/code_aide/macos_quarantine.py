"""Remove quarantine from tool-owned install artifacts on macOS."""

import os
import platform
import re
import shutil
import subprocess
from typing import Any

from code_aide.console import info, run_command, warning

QUARANTINE = "com.apple.quarantine"


def clear_quarantine(path: str) -> bool:
    """Clear only quarantine, without following symlinks inside an install tree.

    Callers supply a package directory, verified bundle, or resolved executable,
    never a shared bin directory. No sudo or interactive approval is attempted.
    """
    if platform.system() != "Darwin":
        return True
    try:
        # macOS Python does not expose os.removexattr. Apple's utility treats
        # missing attributes as success with -r; -s never dereferences links.
        run_command(["/usr/bin/xattr", "-r", "-d", "-s", QUARANTINE, path], timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        detail = (
            exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        )
        warning(f"Could not clear macOS quarantine at {path}: {detail}")
        warning("Installation files remain in place; fix their permissions and retry.")
        return False
    info(f"Cleared macOS quarantine from installed artifacts in {path}")
    return True


def clear_npm_quarantine(package: str, prefix_args: list[str] | None = None) -> bool:
    """Clear the installed package, including its nested native dependencies."""
    if platform.system() != "Darwin":
        return True
    # Only package names, never paths, tags, URLs, or a whole npm scope.
    if not re.fullmatch(r"(?:@[\w.-]+/)?[\w.-]+", package) or any(
        part in (".", "..") for part in package.lstrip("@").split("/")
    ):
        warning(
            f"Cannot locate installed npm package for quarantine cleanup: {package}"
        )
        return False
    try:
        root = run_command(
            ["npm", "root", "-g", *(prefix_args or [])], timeout=30
        ).stdout.strip()
        if not os.path.isabs(root):
            raise ValueError("npm did not report an absolute global package directory")
        target = os.path.join(root, package)
        if os.path.realpath(target) != os.path.join(os.path.realpath(root), package):
            raise ValueError(
                "the installed npm package is linked outside its directory"
            )
        return clear_quarantine(target)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        warning(f"Could not clear macOS quarantine for {package}: {exc}")
        return False


def clear_script_quarantine(cfg: dict[str, Any]) -> bool:
    """Clear configured script artifacts and the resolved command, if present."""
    if platform.system() != "Darwin":
        return True
    paths = [os.path.expanduser(p) for p in cfg.get("macos_quarantine_paths", [])]
    command = shutil.which(cfg["command"])
    if command:
        paths.append(command)
    succeeded = True
    for path in dict.fromkeys(paths):
        if os.path.exists(path):
            succeeded = clear_quarantine(os.path.realpath(path)) and succeeded
    return succeeded


def clear_brew_quarantine(package: str, *, cask: bool) -> bool:
    """Clear one Homebrew package's artifacts after a successful upgrade."""
    if platform.system() != "Darwin":
        return True
    try:
        path = run_command(
            ["brew", "--caskroom" if cask else "--prefix", package], timeout=30
        ).stdout.strip()
        if not os.path.isabs(path) or os.path.basename(path) != package.split("/")[-1]:
            raise ValueError("Homebrew did not report the requested package directory")
        return clear_quarantine(os.path.realpath(path))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        warning(f"Could not clear macOS quarantine for {package}: {exc}")
        return False

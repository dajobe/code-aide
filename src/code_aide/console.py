"""Console output and subprocess helpers for CLI modules."""

import shutil
import subprocess
from typing import List

from code_aide.constants import Colors


def info(message: str) -> None:
    """Print info message."""
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {message}")


def success(message: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {message}")


def warning(message: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}[WARNING]{Colors.NC} {message}")


def error(message: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}[ERROR]{Colors.NC} {message}")


def command_exists(command: str) -> bool:
    """Check if a command exists in PATH."""
    return shutil.which(command) is not None


def run_command(
    cmd: List[str], check: bool = True, capture: bool = True
) -> subprocess.CompletedProcess:
    """Run a command and return the result.

    With ``check=True`` (default) this raises ``CalledProcessError`` on
    non-zero exit, matching ``subprocess.run`` semantics.
    """
    if capture:
        return subprocess.run(
            cmd,
            check=check,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
    return subprocess.run(
        cmd,
        check=check,
        stdin=subprocess.DEVNULL,
    )

"""Console output and subprocess helpers for CLI modules."""

import shutil
import subprocess
from typing import List, Union

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
) -> Union[subprocess.CompletedProcess, subprocess.CalledProcessError]:
    """Run a command and return the result."""
    try:
        if capture:
            result = subprocess.run(
                cmd,
                check=check,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
            )
        else:
            result = subprocess.run(
                cmd,
                check=check,
                stdin=subprocess.DEVNULL,
            )
        return result
    except subprocess.CalledProcessError as exc:
        if check:
            raise
        return exc

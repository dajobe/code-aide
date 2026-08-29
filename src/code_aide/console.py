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
    """Run a tool-mutating command with consistent hardening.

    Forces ``stdin=subprocess.DEVNULL`` so an interactive prompt (sudo
    without cached creds, npm asking for telemetry consent, etc.) cannot
    block the install on terminal input — the symptom would be a
    silently hung process. Use this wrapper for install/upgrade/remove
    commands; use ``subprocess.run`` directly for probing commands that
    need ``timeout=`` or ``check=False``.

    Defaults to capture+text mode. With ``check=True`` (default) a
    non-zero exit raises ``CalledProcessError``.
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


def called_process_error_message(exc: subprocess.CalledProcessError) -> str:
    """Return the best available error output from a failed command.

    Commands run with ``capture=False`` leave ``exc.stderr`` as None
    because their output already went straight to the terminal; fall
    back to captured stdout, then to the exception summary.
    """
    return exc.stderr or exc.stdout or str(exc)

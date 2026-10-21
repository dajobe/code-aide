"""Private download-cache lifetimes for npm commands and installer scripts."""

from contextlib import contextmanager
import os
import signal
import subprocess
from pathlib import Path
import tempfile
from typing import Any, Iterator, Mapping


@contextmanager
def npm_cache_environment(
    env: Mapping[str, str] | None = None,
) -> Iterator[dict[str, str]]:
    """Keep downloads on the home filesystem and remove only this invocation."""
    root = Path.home() / ".cache" / "code-aide" / "npm-operations"
    current = Path.home()
    for component in (".cache", "code-aide", "npm-operations"):
        current = current / component
        if current.is_symlink():
            raise ValueError(f"npm operation cache parent is a symlink: {current}")
        current.mkdir(exist_ok=True, mode=0o700)
        if current.stat().st_uid != os.getuid():
            raise ValueError(f"npm operation cache parent has another owner: {current}")
    with tempfile.TemporaryDirectory(prefix="operation-", dir=root) as directory:
        child_env = dict(os.environ if env is None else env)
        # npm treats config environment keys case-insensitively.
        for key in list(child_env):
            if key.lower() == "npm_config_cache":
                del child_env[key]
        child_env["npm_config_cache"] = directory
        yield child_env


def stop_process_group(process: subprocess.Popen) -> None:
    """Stop the entire private process group before its cache is removed."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.communicate(timeout=5)


def run_npm_process(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    """Run npm in its own session and reap its children on cancellation."""
    check = kwargs.pop("check", True)
    timeout = kwargs.pop("timeout", None)
    if kwargs.pop("capture_output", False):
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    with subprocess.Popen(cmd, start_new_session=True, **kwargs) as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except BaseException:
            stop_process_group(process)
            raise
        result = subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)
        if check:
            result.check_returncode()
        return result

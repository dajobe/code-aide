"""Snapshot files before an install script runs and restore them afterwards.

Some third-party installers edit shell profiles unconditionally. A tool's
``install_preserve_files`` lists files that code-aide puts back exactly as
they were once the script finishes, including symlinks into a dotfiles
repository and files the script created that did not exist before.
"""

import contextlib
import os
import stat
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Sequence

from code_aide.console import info, warning


@dataclass
class _FileState:
    path: str
    real_path: str
    link: Optional[str] = None
    content: Optional[bytes] = None
    mode: Optional[int] = None
    missing_dirs: List[str] = field(default_factory=list)


def get_install_preserve_files(tool_config: Dict[str, Any]) -> Optional[List[str]]:
    """Return the files a tool's install script must leave unchanged."""
    paths = tool_config.get("install_preserve_files")
    return list(paths) if paths else None


def _missing_ancestors(path: str) -> List[str]:
    """Return the ancestors of path that do not exist, deepest first."""
    missing = []
    parent = os.path.dirname(path)
    while parent and not os.path.lexists(parent):
        missing.append(parent)
        next_parent = os.path.dirname(parent)
        if next_parent == parent:
            break
        parent = next_parent
    return missing


def snapshot_file(path: str) -> _FileState:
    """Record a file's symlink, content, and mode, or that it is absent."""
    path = os.path.expanduser(path)
    state = _FileState(path=path, real_path=os.path.realpath(path))
    if os.path.islink(path):
        state.link = os.readlink(path)
    if os.path.isfile(state.real_path):
        with open(state.real_path, "rb") as handle:
            state.content = handle.read()
        state.mode = stat.S_IMODE(os.stat(state.real_path).st_mode)
    else:
        state.missing_dirs = _missing_ancestors(state.real_path)
    return state


def _remove_path(path: str) -> None:
    if os.path.islink(path) or os.path.isfile(path):
        os.remove(path)


def restore_file(state: _FileState) -> bool:
    """Put a file back as snapshotted; return True when anything changed."""
    changed = False
    path = state.path
    if state.link is not None:
        if not os.path.islink(path) or os.readlink(path) != state.link:
            _remove_path(path)
            os.symlink(state.link, path)
            changed = True
    elif os.path.islink(path):
        os.remove(path)
        changed = True

    real_path = state.real_path
    if state.content is None:
        if os.path.isfile(real_path):
            os.remove(real_path)
            changed = True
        for directory in state.missing_dirs:
            with contextlib.suppress(OSError):
                os.rmdir(directory)
        return changed

    current = None
    if os.path.isfile(real_path) and not os.path.islink(real_path):
        with open(real_path, "rb") as handle:
            current = handle.read()
    elif os.path.lexists(real_path):
        _remove_path(real_path)
    if current != state.content:
        with open(real_path, "wb") as handle:
            handle.write(state.content)
        changed = True
    if state.mode is not None and stat.S_IMODE(os.stat(real_path).st_mode) != (
        state.mode
    ):
        os.chmod(real_path, state.mode)
        changed = True
    return changed


@contextlib.contextmanager
def preserved_files(paths: Optional[Sequence[str]]) -> Iterator[None]:
    """Restore each path to its prior state when the block exits."""
    states = []
    for path in paths or ():
        try:
            states.append(snapshot_file(path))
        except OSError as exc:
            warning(f"Could not snapshot {path}; it will not be restored: {exc}")
    try:
        yield
    finally:
        for state in states:
            try:
                if restore_file(state):
                    info(f"Restored {state.path} after the install script changed it")
            except OSError as exc:
                warning(f"Could not restore {state.path}: {exc}")

"""Helpers for direct-download tools that publish versioned release assets.

These cover optional ``tools.json`` keys used by direct-download tools whose
upstream publishes a checksum file and expects a particular on-disk layout:

* ``checksums_url_template``: URL of an upstream ``SHA256SUMS`` file, formatted
  with ``{version}``, ``{os}`` and ``{arch}``.
* ``unsupported_platforms``: mapping of ``"<os>-<arch>"`` to an explanation.
* ``install_complete_marker``: file written into the version directory, holding
  the version, once extraction finishes.
* ``launcher_record_file``: file listing launcher paths, one per line, that the
  tool reads so its own pruning keeps the version the launcher points at.
"""

import os
from typing import Any, Dict, Iterable, Optional


def parse_sha256sums(text: str, filename: str) -> Optional[str]:
    """Return the SHA256 for ``filename`` from ``sha256sum``-format text.

    Accepts both text-mode (``hash  name``) and binary-mode (``hash *name``)
    lines. Returns None when the file is not listed.
    """
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        digest, name = parts
        if name.startswith("*"):
            name = name[1:]
        if name == filename and len(digest) == 64:
            return digest.lower()
    return None


def unsupported_platform_message(
    tool_config: Dict[str, Any], os_name: str, arch: str
) -> Optional[str]:
    """Return the configured explanation when this platform has no download."""
    unsupported = tool_config.get("unsupported_platforms") or {}
    return unsupported.get(f"{os_name}-{arch}")


def install_marker_matches(
    tool_config: Dict[str, Any], install_dir: str, version: str
) -> bool:
    """Return True when the version directory already holds a complete install."""
    marker = tool_config.get("install_complete_marker")
    if not marker:
        return False
    try:
        with open(os.path.join(install_dir, marker), encoding="utf-8") as handle:
            return handle.read().strip() == version
    except OSError:
        return False


def write_install_marker(
    tool_config: Dict[str, Any], install_dir: str, version: str
) -> None:
    """Write the completion marker, when configured, into ``install_dir``."""
    marker = tool_config.get("install_complete_marker")
    if not marker:
        return
    with open(os.path.join(install_dir, marker), "w", encoding="utf-8") as handle:
        handle.write(f"{version}\n")


def record_launchers(tool_config: Dict[str, Any], link_paths: Iterable[str]) -> None:
    """Append launcher paths to the tool's launcher record file, if configured.

    Paths already recorded are skipped. Each path is resolved through its
    directory (not the link itself), matching what the tool writes.
    """
    record_file = tool_config.get("launcher_record_file")
    if not record_file:
        return
    record_path = os.path.expanduser(record_file)
    try:
        with open(record_path, encoding="utf-8") as handle:
            recorded = {line.strip() for line in handle}
    except OSError:
        recorded = set()

    new_entries = []
    for link_path in link_paths:
        launcher = os.path.join(
            os.path.realpath(os.path.dirname(link_path)), os.path.basename(link_path)
        )
        if launcher not in recorded:
            new_entries.append(launcher)
            recorded.add(launcher)
    if not new_entries:
        return

    os.makedirs(os.path.dirname(record_path), exist_ok=True)
    # Start on a fresh line in case another writer left a partial line.
    with open(record_path, "a", encoding="utf-8") as handle:
        handle.write("\n" + "".join(f"{entry}\n" for entry in new_entries))

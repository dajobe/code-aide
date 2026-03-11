"""Status helpers for installed tools and version reporting."""

import subprocess
from typing import Any, Dict, Optional

from code_aide.constants import Colors
from code_aide.prereqs import is_tool_installed
from code_aide.versions import (
    extract_version_from_string,
    normalize_version,
    status_version_matches_latest,
    version_is_newer,
)


def print_system_version_status(
    cli_version: str,
    latest_version: Optional[str],
    pkg_info: Dict[str, Optional[str]],
) -> None:
    """Print version status for a system-package-managed tool."""
    installed_ver = extract_version_from_string(cli_version)
    avail_ver = pkg_info.get("available_version")
    avail_date = pkg_info.get("available_date")

    pkg_up_to_date = True
    if installed_ver and avail_ver:
        pkg_up_to_date = installed_ver == normalize_version(
            avail_ver
        ) or version_is_newer(installed_ver, normalize_version(avail_ver))

    if pkg_up_to_date:
        print(f"  Version:      {cli_version} {Colors.GREEN}(up to date){Colors.NC}")
    else:
        print(
            f"  Version:      {cli_version} {Colors.YELLOW}(package has {avail_ver})"
            f"{Colors.NC}"
        )

    if avail_ver:
        date_suffix = f", {avail_date}" if avail_date else ""
        pkg_name = pkg_info.get("package") or "system"
        # Only show upstream when config's latest is newer than packaged version;
        # avoid showing a stale "upstream" that is older than what's installed.
        show_upstream = (
            latest_version
            and not status_version_matches_latest(avail_ver, latest_version)
            and version_is_newer(
                normalize_version(latest_version), normalize_version(avail_ver)
            )
        )
        if show_upstream:
            print(
                f"  Packaged:     {avail_ver} ({pkg_name}{date_suffix}) "
                f"{Colors.YELLOW}(upstream: {latest_version}){Colors.NC}"
            )
        else:
            print(f"  Packaged:     {avail_ver} ({pkg_name}{date_suffix})")


def print_brew_version_status(
    cli_version: str,
    latest_version: Optional[str],
    pkg_info: Dict[str, Optional[str]],
) -> None:
    """Print version status for a Homebrew-managed tool."""
    avail_ver = pkg_info.get("available_version")
    outdated = pkg_info.get("outdated")

    if outdated:
        print(
            f"  Version:      {cli_version} {Colors.YELLOW}(Homebrew has {avail_ver})"
            f"{Colors.NC}"
        )
    else:
        print(f"  Version:      {cli_version} {Colors.GREEN}(up to date){Colors.NC}")

    if avail_ver:
        pkg_name = pkg_info.get("package") or "Homebrew"
        # Only show upstream when config's latest is newer than packaged version;
        # avoid showing a stale "upstream" that is older than what's installed.
        show_upstream = (
            latest_version
            and not status_version_matches_latest(avail_ver, latest_version)
            and version_is_newer(
                normalize_version(latest_version), normalize_version(avail_ver)
            )
        )
        if show_upstream:
            print(
                f"  Packaged:     {avail_ver} ({pkg_name}) "
                f"{Colors.YELLOW}(upstream: {latest_version}){Colors.NC}"
            )
        else:
            print(f"  Packaged:     {avail_ver} ({pkg_name})")


def get_tool_status(tool_name: str, tool_config: Dict[str, Any]) -> Dict[str, Any]:
    """Get status information for a specific tool."""
    status_info = {
        "installed": is_tool_installed(tool_name),
        "version": None,
        "user": None,
        "usage": None,
        "errors": [],
    }

    if not status_info["installed"]:
        return status_info

    command = tool_config["command"]
    version_args = tool_config.get("version_args", ["--version"])
    cmd = [command] + version_args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode == 0 and result.stdout.strip():
            status_info["version"] = result.stdout.strip().split("\n")[0]
    except subprocess.TimeoutExpired:
        status_info["errors"].append("Version check timed out after 10s")
    except Exception:
        pass

    return status_info

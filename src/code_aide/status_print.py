"""Rendering helpers that print version-status lines for managed tools.

Split out of :mod:`code_aide.status` so the status module can stay focused
on the upgrade-decision logic. The three public functions remain importable
from :mod:`code_aide.status` for backwards compatibility.
"""

from typing import Optional

from code_aide.constants import Colors
from code_aide.detection_types import PackageVersionInfo
from code_aide.versions import (
    extract_version_from_string,
    normalize_version,
    status_version_matches_latest,
    version_is_newer,
)

PackageInfo = PackageVersionInfo


def _print_packaged_version_status(
    cli_version: str,
    latest_version: Optional[str],
    pkg_info: PackageInfo,
    *,
    source_label: str,
    default_pkg_name: str,
    pkg_suffix: str,
    is_outdated: bool,
) -> None:
    """Shared rendering for system / brew / pkg "version + packaged" lines.

    Caller decides whether the install is outdated and what to label the
    package source as; this function emits the two lines (Version + Packaged)
    consistently.
    """
    avail_ver = pkg_info.get("available_version")

    if is_outdated:
        print(
            f"  Version:      {cli_version} {Colors.YELLOW}"
            f"({source_label} has {avail_ver}){Colors.NC}"
        )
    else:
        print(f"  Version:      {cli_version} {Colors.GREEN}(up to date){Colors.NC}")

    if not avail_ver:
        return

    pkg_name = pkg_info.get("package") or default_pkg_name
    show_upstream = (
        latest_version
        and not status_version_matches_latest(avail_ver, latest_version)
        and version_is_newer(
            normalize_version(latest_version), normalize_version(avail_ver)
        )
    )
    if show_upstream:
        print(
            f"  Packaged:     {avail_ver} ({pkg_name}{pkg_suffix}) "
            f"{Colors.YELLOW}(upstream: {latest_version}){Colors.NC}"
        )
    else:
        print(f"  Packaged:     {avail_ver} ({pkg_name}{pkg_suffix})")


def print_system_version_status(
    cli_version: str,
    latest_version: Optional[str],
    pkg_info: PackageInfo,
) -> None:
    """Print version status for a system-package-managed tool."""
    installed_ver = extract_version_from_string(cli_version)
    avail_ver = pkg_info.get("available_version")
    is_outdated = bool(
        installed_ver
        and avail_ver
        and installed_ver != normalize_version(avail_ver)
        and not version_is_newer(installed_ver, normalize_version(avail_ver))
    )
    avail_date = pkg_info.get("available_date")
    _print_packaged_version_status(
        cli_version,
        latest_version,
        pkg_info,
        source_label="package",
        default_pkg_name="system",
        pkg_suffix=f", {avail_date}" if avail_date else "",
        is_outdated=is_outdated,
    )


def print_brew_version_status(
    cli_version: str,
    latest_version: Optional[str],
    pkg_info: PackageInfo,
) -> None:
    """Print version status for a Homebrew-managed tool."""
    _print_packaged_version_status(
        cli_version,
        latest_version,
        pkg_info,
        source_label="Homebrew",
        default_pkg_name="Homebrew",
        pkg_suffix="",
        is_outdated=bool(pkg_info.get("outdated")),
    )


def print_pkg_version_status(
    cli_version: str,
    latest_version: Optional[str],
    pkg_info: PackageInfo,
    repo: Optional[str] = None,
) -> None:
    """Print version status for a FreeBSD pkg-managed tool."""
    _print_packaged_version_status(
        cli_version,
        latest_version,
        pkg_info,
        source_label="pkg",
        default_pkg_name="FreeBSD pkg",
        pkg_suffix=f", {repo}" if repo else "",
        is_outdated=bool(pkg_info.get("outdated")),
    )

"""Shared TypedDicts used by detection and package_info modules.

Kept in a separate module to avoid a circular import between
:mod:`code_aide.detection` and :mod:`code_aide.package_info`.
"""

from typing import Optional, TypedDict

from code_aide.install_types import InstallMethod


class DetectedInstallInfo(TypedDict):
    """How a locally installed tool was detected."""

    method: Optional[InstallMethod]
    detail: Optional[str]


class PackageVersionInfo(TypedDict, total=False):
    """Package version info from a system, brew, or FreeBSD pkg lookup."""

    package: Optional[str]
    installed_version: Optional[str]
    available_version: Optional[str]
    available_date: Optional[str]
    outdated: Optional[bool]

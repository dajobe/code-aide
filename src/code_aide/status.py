"""Status helpers for installed tools and version reporting."""

import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, Optional

from code_aide.constants import Colors
from code_aide.detection import (
    detect_install_method,
    get_brew_package_info,
    get_system_package_info,
    is_install_method_deprecated,
)
from code_aide.prereqs import is_tool_installed
from code_aide.versions import (
    extract_version_from_string,
    normalize_version,
    status_version_matches_latest,
    version_is_newer,
)

ToolStatus = Dict[str, Any]
InstallInfo = Dict[str, Optional[str]]
PackageInfo = Dict[str, Any]


class UpgradeDecision(Enum):
    """Normalized upgrade decision used by status and upgrade selection."""

    CURRENT = auto()
    UPGRADE = auto()
    MIGRATION = auto()
    PACKAGE_MANAGED = auto()
    NOT_INSTALLED = auto()
    UNKNOWN = auto()


class VersionDisplayState(Enum):
    """Version relationship for CLI display."""

    UP_TO_DATE = auto()
    OUTDATED = auto()
    UNAVAILABLE = auto()


@dataclass(frozen=True)
class ToolUpgradeAssessment:
    """Typed evaluation result for one tool."""

    decision: UpgradeDecision
    version_state: VersionDisplayState
    actionable_by_upgrade: bool
    latest_version: Optional[str]
    installed_version: Optional[str]
    install_method: Optional[str]
    install_detail: Optional[str]
    status: ToolStatus
    package_info: Optional[PackageInfo] = None


class ToolUpgradeEvaluator:
    """Evaluate one tool consistently for status and default upgrade."""

    def __init__(
        self,
        tool_name: str,
        tool_config: Dict[str, Any],
        *,
        status: Optional[ToolStatus] = None,
        install_info: Optional[InstallInfo] = None,
        package_info: Optional[PackageInfo] = None,
        tool_path: Optional[str] = None,
    ) -> None:
        self.tool_name = tool_name
        self.tool_config = tool_config
        self._status = status
        self._install_info = install_info
        self._package_info = package_info
        self._tool_path = tool_path

    def evaluate(self) -> ToolUpgradeAssessment:
        """Return the normalized typed result for this tool."""
        status = self._get_status()
        if not status.get("installed", True):
            return self._result(
                decision=UpgradeDecision.NOT_INSTALLED,
                version_state=VersionDisplayState.UNAVAILABLE,
                status=status,
            )

        install_info = self._get_install_info()
        method = install_info.get("method")
        configured = self.tool_config.get("install_type")
        package_info = self._get_package_info(method, install_info)
        version_state = self._catalog_version_state(status.get("version"))

        if is_install_method_deprecated(method, configured):
            return self._result(
                decision=UpgradeDecision.MIGRATION,
                version_state=version_state,
                status=status,
                install_info=install_info,
                package_info=package_info,
            )

        if method in ("brew_formula", "brew_cask"):
            return self._evaluate_brew(status, install_info, package_info)

        if method == "system":
            return self._result(
                decision=UpgradeDecision.PACKAGE_MANAGED,
                version_state=self._system_version_state(
                    status.get("version"), package_info
                ),
                status=status,
                install_info=install_info,
                package_info=package_info,
            )

        return self._evaluate_catalog(status, install_info, package_info)

    def _evaluate_brew(
        self,
        status: ToolStatus,
        install_info: InstallInfo,
        package_info: Optional[PackageInfo],
    ) -> ToolUpgradeAssessment:
        cli_version = status.get("version")
        if cli_version and package_info and package_info.get("outdated") is True:
            return self._result(
                decision=UpgradeDecision.UPGRADE,
                version_state=VersionDisplayState.OUTDATED,
                status=status,
                install_info=install_info,
                package_info=package_info,
            )

        if cli_version and package_info and package_info.get("outdated") is False:
            return self._result(
                decision=UpgradeDecision.CURRENT,
                version_state=VersionDisplayState.UP_TO_DATE,
                status=status,
                install_info=install_info,
                package_info=package_info,
            )

        return self._evaluate_catalog(status, install_info, package_info)

    def _evaluate_catalog(
        self,
        status: ToolStatus,
        install_info: InstallInfo,
        package_info: Optional[PackageInfo],
    ) -> ToolUpgradeAssessment:
        version_state = self._catalog_version_state(status.get("version"))
        if version_state == VersionDisplayState.UP_TO_DATE:
            decision = UpgradeDecision.CURRENT
        elif version_state == VersionDisplayState.OUTDATED:
            decision = UpgradeDecision.UPGRADE
        else:
            decision = UpgradeDecision.UNKNOWN

        return self._result(
            decision=decision,
            version_state=version_state,
            status=status,
            install_info=install_info,
            package_info=package_info,
        )

    def _result(
        self,
        *,
        decision: UpgradeDecision,
        version_state: VersionDisplayState,
        status: ToolStatus,
        install_info: Optional[InstallInfo] = None,
        package_info: Optional[PackageInfo] = None,
    ) -> ToolUpgradeAssessment:
        if install_info is None:
            install_info = {"method": None, "detail": None}

        return ToolUpgradeAssessment(
            decision=decision,
            version_state=version_state,
            actionable_by_upgrade=decision
            in (UpgradeDecision.UPGRADE, UpgradeDecision.MIGRATION),
            latest_version=self.tool_config.get("latest_version"),
            installed_version=status.get("version"),
            install_method=install_info.get("method"),
            install_detail=install_info.get("detail"),
            status=status,
            package_info=package_info,
        )

    def _get_status(self) -> ToolStatus:
        if self._status is None:
            self._status = get_tool_status(self.tool_name, self.tool_config)
        self._status.setdefault("installed", True)
        self._status.setdefault("errors", [])
        return self._status

    def _get_install_info(self) -> InstallInfo:
        if self._install_info is None:
            self._install_info = detect_install_method(self.tool_name)
        return self._install_info

    def _get_package_info(
        self, method: Optional[str], install_info: InstallInfo
    ) -> Optional[PackageInfo]:
        if self._package_info is not None:
            return self._package_info

        if method in ("brew_formula", "brew_cask"):
            self._package_info = get_brew_package_info(
                method, install_info.get("detail")
            )
        elif method == "system":
            tool_path = self._tool_path or shutil.which(self.tool_config["command"])
            self._package_info = (
                get_system_package_info(tool_path) if tool_path else None
            )
        else:
            self._package_info = None

        return self._package_info

    def _catalog_version_state(self, cli_version: Optional[str]) -> VersionDisplayState:
        latest_version = self.tool_config.get("latest_version")
        if not cli_version or not latest_version:
            return VersionDisplayState.UNAVAILABLE

        if _version_matches_or_exceeds_latest(cli_version, latest_version):
            return VersionDisplayState.UP_TO_DATE

        return VersionDisplayState.OUTDATED

    @staticmethod
    def _system_version_state(
        cli_version: Optional[str], package_info: Optional[PackageInfo]
    ) -> VersionDisplayState:
        if not cli_version:
            return VersionDisplayState.UNAVAILABLE

        if not package_info:
            return VersionDisplayState.UP_TO_DATE

        avail_ver = package_info.get("available_version")
        installed_ver = extract_version_from_string(cli_version)
        if not avail_ver or not installed_ver:
            return VersionDisplayState.UP_TO_DATE

        normalized_available = normalize_version(avail_ver)
        if installed_ver == normalized_available or version_is_newer(
            installed_ver, normalized_available
        ):
            return VersionDisplayState.UP_TO_DATE

        return VersionDisplayState.OUTDATED


def _version_matches_or_exceeds_latest(
    cli_version: Optional[str], latest_version: Optional[str]
) -> bool:
    """Return True when the installed version should be treated as current."""
    if not cli_version or not latest_version:
        return False

    if status_version_matches_latest(cli_version, latest_version):
        return True

    installed_ver = extract_version_from_string(cli_version)
    return bool(installed_ver and version_is_newer(installed_ver, latest_version))


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

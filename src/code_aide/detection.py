"""Install-method detection helpers.

Package version info lookups (system / brew / pkg) live in
:mod:`code_aide.package_info`; the symbols are re-exported here for
backwards compatibility with existing callers.
"""

import logging
import os
import platform
import re
import shutil
import subprocess
from typing import Optional

from code_aide.app_bundle import (
    detect_app_install,
    is_app_bundle_tool,
    is_brew_cask_installed,
    is_cask_app,
)
from code_aide.constants import TOOLS
from code_aide.console import command_exists
from code_aide.detection_types import DetectedInstallInfo, PackageVersionInfo
from code_aide.install_types import (
    InstallMethod,
    InstallMethodInput,
    InstallType,
    InstallTypeInput,
    get_tool_install_type,
    install_method_from_type,
    parse_install_method,
    parse_install_type,
)
from code_aide.package_info import (
    get_brew_package_info,
    get_pkg_package_info,
    get_system_package_info,
)

_logger = logging.getLogger(__name__)

__all__ = [
    "DetectedInstallInfo",
    "PackageVersionInfo",
    "detect_install_method",
    "detect_install_method_at",
    "format_install_method",
    "format_migration_warning",
    "get_brew_package_info",
    "get_pkg_package_info",
    "get_system_package_info",
    "is_brew_cask_installed",
    "is_deprecated_install",
    "is_freebsd",
    "is_install_method_deprecated",
]


def is_freebsd() -> bool:
    """Return True when running on FreeBSD."""
    return platform.system() == "FreeBSD"


def _pkg_owns_file(path: str) -> bool:
    """Return True when FreeBSD pkg owns the given file path."""
    if not command_exists("pkg"):
        return False
    try:
        proc = subprocess.run(
            ["pkg", "which", "-q", path],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        return proc.returncode == 0 and bool(proc.stdout.strip())
    except Exception:
        _logger.debug("pkg which lookup failed for %s", path, exc_info=True)
        return False


# A desktop app's CLI shim names the app executable on a line like
# app='/Applications/Example.app/Contents/MacOS/Example'
_SHIM_APP_RE = re.compile(r"^app='([^']+?\.app)/", re.MULTILINE)


def _cask_bundle_name(cask: str) -> Optional[str]:
    """Return the bundle name of the app tool that installs from this cask."""
    for tool_config in TOOLS.values():
        if tool_config.get("brew_cask") == cask and tool_config.get("app_bundle_name"):
            return str(tool_config["app_bundle_name"])
    return None


def _detect_desktop_cli(
    tool_config: dict, real_path: str
) -> Optional[DetectedInstallInfo]:
    """Detect a command provided by a desktop app's CLI shim.

    Some desktop apps install their command as a shell shim that
    runs the app bundle, so the command never resolves into the Caskroom.
    Reports the Homebrew cask when it owns the app, otherwise the app bundle
    as a user-managed install.
    """
    shim = tool_config.get("desktop_cli_shim")
    if not shim or os.path.realpath(os.path.expanduser(shim)) != real_path:
        return None
    try:
        with open(real_path, encoding="utf-8", errors="replace") as handle:
            content = handle.read(65536)
    except OSError:
        return None
    match = _SHIM_APP_RE.search(content)
    if not match:
        return None
    app_bundle = match.group(1)

    cask = tool_config.get("brew_cask")
    if cask and is_cask_app(app_bundle, cask, _cask_bundle_name(cask)):
        return {"method": InstallMethod.BREW_CASK, "detail": cask}
    return {"method": InstallMethod.SYSTEM, "detail": app_bundle}


def _empty_install_info() -> DetectedInstallInfo:
    """Return the default empty install-info shape."""
    return {"method": None, "detail": None}


def detect_install_method(tool_name: str) -> DetectedInstallInfo:
    """Detect how a tool was actually installed."""
    tool_config = TOOLS.get(tool_name)
    if not tool_config:
        return _empty_install_info()

    if is_app_bundle_tool(tool_config):
        return detect_app_install(tool_config)

    command_path = shutil.which(tool_config["command"])
    if not command_path:
        return _empty_install_info()

    return detect_install_method_at(tool_config, command_path)


def detect_install_method_at(
    tool_config: dict, command_path: str
) -> DetectedInstallInfo:
    """Detect how the command at a specific path was installed."""
    real_path = os.path.realpath(command_path)

    cellar_match = re.search(r"/Cellar/([^/]+)/", real_path)
    if cellar_match:
        return {"method": InstallMethod.BREW_FORMULA, "detail": cellar_match.group(1)}

    caskroom_match = re.search(r"/Caskroom/([^/]+)/", real_path)
    if caskroom_match:
        return {"method": InstallMethod.BREW_CASK, "detail": caskroom_match.group(1)}

    desktop_info = _detect_desktop_cli(tool_config, real_path)
    if desktop_info:
        return desktop_info

    if "/.local/share/claude/versions/" in real_path:
        return {"method": InstallMethod.SCRIPT, "detail": "native installer"}

    if "/node_modules/" in real_path:
        npm_package = tool_config.get("npm_package")
        if not npm_package:
            match = re.search(r"/node_modules/((?:@[^/]+/)?[^/]+)", real_path)
            if match:
                npm_package = match.group(1)
        return {"method": InstallMethod.NPM, "detail": npm_package}

    system_prefixes = ("/opt/", "/usr/bin/", "/usr/sbin/", "/usr/local/bin/")
    if any(real_path.startswith(prefix) for prefix in system_prefixes):
        freebsd_port = tool_config.get("freebsd_port")
        if is_freebsd() and freebsd_port and _pkg_owns_file(real_path):
            return {"method": InstallMethod.PKG, "detail": freebsd_port}
        return {"method": InstallMethod.SYSTEM, "detail": real_path}

    return {
        "method": install_method_from_type(get_tool_install_type(tool_config)),
        "detail": None,
    }


def format_install_method(method: InstallMethodInput, detail: Optional[str]) -> str:
    """Format detected local install method for display."""
    install_method = parse_install_method(method)
    install_type = parse_install_type(method)
    if install_method == InstallMethod.BREW_FORMULA:
        return f"Homebrew formula ({detail})" if detail else "Homebrew formula"
    if install_method == InstallMethod.BREW_CASK:
        return f"Homebrew cask ({detail})" if detail else "Homebrew cask"
    if install_method == InstallMethod.NPM:
        return f"npm ({detail})" if detail else "npm"
    if install_method == InstallMethod.BREW_NPM:
        return (
            f"Homebrew prefix npm-global ({detail})"
            if detail
            else "Homebrew prefix npm-global"
        )
    if install_method == InstallMethod.PKG:
        return f"FreeBSD pkg ({detail})" if detail else "FreeBSD pkg"
    if install_method == InstallMethod.SYSTEM:
        if detail and detail.endswith(".app"):
            return f"desktop app ({detail})"
        return f"system package ({detail})" if detail else "system package"
    if install_method == InstallMethod.APP_BUNDLE:
        return f"app bundle ({detail})" if detail else "app bundle"
    if install_method == InstallMethod.SCRIPT or install_type == InstallType.SCRIPT:
        return "script"
    if (
        install_method == InstallMethod.DIRECT_DOWNLOAD
        or install_type == InstallType.DIRECT_DOWNLOAD
    ):
        return "direct download"
    if method:
        return str(method)
    return "unknown"


# Install methods that are user-managed and never considered deprecated
_USER_MANAGED_METHODS = frozenset(
    {
        InstallMethod.BREW_FORMULA,
        InstallMethod.BREW_CASK,
        InstallMethod.SYSTEM,
        InstallMethod.PKG,
    }
)

# Install methods that are considered deprecated when they don't match
# the configured install_type
_DEPRECATED_METHODS = frozenset({InstallMethod.NPM, InstallMethod.BREW_NPM})


def is_install_method_deprecated(
    detected: InstallMethodInput, configured: InstallTypeInput | None
) -> bool:
    """Return True when a detected method should be migrated by code-aide."""
    detected_method = parse_install_method(detected)
    configured_type = parse_install_type(configured)
    if not detected_method or not configured_type:
        return False

    if detected_method in _USER_MANAGED_METHODS:
        return False

    return (
        detected_method in _DEPRECATED_METHODS
        and detected_method != install_method_from_type(configured_type)
    )


def is_deprecated_install(tool_name: str) -> bool:
    """Check if a tool's detected install method is deprecated.

    Returns True when the detected install method is npm or brew_npm
    but the configured install_type is something else (e.g. script,
    direct_download).  Brew formula/cask and system installs are
    user-managed and never considered deprecated.
    """
    tool_config = TOOLS.get(tool_name)
    if not tool_config:
        return False

    install_info = detect_install_method(tool_name)
    detected = parse_install_method(install_info["method"])

    if not detected:
        return False

    if detected in _USER_MANAGED_METHODS:
        return False

    configured = tool_config.get("install_type")
    if not configured:
        return False

    return is_install_method_deprecated(detected, configured)


def format_migration_warning(tool_name: str) -> Optional[str]:
    """Return a human-readable migration warning, or None if not needed."""
    if not is_deprecated_install(tool_name):
        return None

    tool_config = TOOLS.get(tool_name)
    if not tool_config:
        return None

    install_info = detect_install_method(tool_name)
    detected_label = format_install_method(
        install_info["method"], install_info["detail"]
    )
    configured_label = format_install_method(tool_config["install_type"], None)

    return (
        f"Installed via {detected_label} but configured method is "
        f"{configured_label}. Run 'code-aide upgrade {tool_name}' to migrate."
    )

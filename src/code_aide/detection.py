"""Install-method and system package detection helpers."""

import glob as globmod
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Dict, Optional

from code_aide.constants import TOOLS
from code_aide.console import command_exists


def detect_install_method(tool_name: str) -> Dict[str, Optional[str]]:
    """Detect how a tool was actually installed."""
    tool_config = TOOLS.get(tool_name)
    if not tool_config:
        return {"method": None, "detail": None}

    command_path = shutil.which(tool_config["command"])
    if not command_path:
        return {"method": None, "detail": None}

    real_path = os.path.realpath(command_path)

    cellar_match = re.search(r"/Cellar/([^/]+)/", real_path)
    if cellar_match:
        return {"method": "brew_formula", "detail": cellar_match.group(1)}

    caskroom_match = re.search(r"/Caskroom/([^/]+)/", real_path)
    if caskroom_match:
        return {"method": "brew_cask", "detail": caskroom_match.group(1)}

    if "/.local/share/claude/versions/" in real_path:
        return {"method": "script", "detail": "native installer"}

    if "/node_modules/" in real_path:
        npm_package = tool_config.get("npm_package")
        if not npm_package:
            match = re.search(r"/node_modules/((?:@[^/]+/)?[^/]+)", real_path)
            if match:
                npm_package = match.group(1)
        return {"method": "npm", "detail": npm_package}

    system_prefixes = ("/opt/", "/usr/bin/", "/usr/sbin/", "/usr/local/bin/")
    if any(real_path.startswith(prefix) for prefix in system_prefixes):
        return {"method": "system", "detail": real_path}

    return {"method": tool_config["install_type"], "detail": None}


def get_system_package_info(binary_path: str) -> Dict[str, Optional[str]]:
    """Get package version info for a system-installed binary."""
    result: Dict[str, Optional[str]] = {
        "package": None,
        "installed_version": None,
        "available_version": None,
        "available_date": None,
    }

    if not command_exists("qfile"):
        return result

    try:
        proc = subprocess.run(
            ["qfile", "-qC", binary_path],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return result
        package = proc.stdout.strip().split("\n")[0]
        result["package"] = package
    except Exception:
        return result

    try:
        proc = subprocess.run(
            ["qlist", "-Iv", package],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            installed_cpv = proc.stdout.strip().split("\n")[0]
            proc2 = subprocess.run(
                ["qatom", "-F", "%{PV}", installed_cpv],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
                stdin=subprocess.DEVNULL,
            )
            if proc2.returncode == 0 and proc2.stdout.strip():
                result["installed_version"] = proc2.stdout.strip()
    except Exception:
        pass

    if "/" not in package:
        return result

    category, package_name = package.split("/", 1)
    ebuild_dirs = globmod.glob(f"/var/db/repos/*/{category}/{package_name}/")
    ebuilds = []
    for ebuild_dir in ebuild_dirs:
        for entry in os.listdir(ebuild_dir):
            if entry.endswith(".ebuild") and entry.startswith(f"{package_name}-"):
                version = entry[len(f"{package_name}-") : -len(".ebuild")]
                ebuild_path = os.path.join(ebuild_dir, entry)
                ebuilds.append((version, ebuild_path))

    if ebuilds:
        best_version = None
        best_path = None
        for version, path in ebuilds:
            if best_version is None:
                best_version = version
                best_path = path
                continue
            try:
                proc = subprocess.run(
                    [
                        "qatom",
                        "-c",
                        f"{package}-{version}",
                        f"{package}-{best_version}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                    stdin=subprocess.DEVNULL,
                )
                if proc.returncode == 0 and ">" in proc.stdout:
                    best_version = version
                    best_path = path
            except Exception:
                pass

        if best_version:
            result["available_version"] = best_version
        if best_path:
            try:
                mtime = os.path.getmtime(best_path)
                result["available_date"] = datetime.fromtimestamp(
                    mtime, tz=timezone.utc
                ).strftime("%Y-%m-%d")
            except Exception:
                pass

    return result


def get_brew_package_info(
    method: str, package_name: Optional[str]
) -> Dict[str, Optional[str]]:
    """Get package version info for a Homebrew-managed tool."""
    result: Dict[str, Optional[str]] = {
        "package": package_name,
        "installed_version": None,
        "available_version": None,
        "available_date": None,
        "outdated": None,
    }

    if method not in ("brew_formula", "brew_cask") or not package_name:
        return result

    if not command_exists("brew"):
        return result

    command = ["brew", "info", "--json=v2"]
    if method == "brew_cask":
        command.append("--cask")
    command.append(package_name)

    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return result

        payload = json.loads(proc.stdout)
        if method == "brew_formula":
            formulae = payload.get("formulae", [])
            if not formulae:
                return result
            formula = formulae[0]
            installed = formula.get("installed", [])
            if installed:
                result["installed_version"] = installed[-1].get("version")
            linked_keg = formula.get("linked_keg")
            if linked_keg:
                result["installed_version"] = linked_keg
            result["available_version"] = formula.get("versions", {}).get("stable")
            result["outdated"] = bool(formula.get("outdated"))
        else:
            casks = payload.get("casks", [])
            if not casks:
                return result
            cask = casks[0]
            installed_version = cask.get("installed")
            if isinstance(installed_version, list):
                installed_version = installed_version[0] if installed_version else None
            result["installed_version"] = installed_version
            result["available_version"] = cask.get("version")
            result["outdated"] = bool(cask.get("outdated"))
    except Exception:
        return result

    return result


def format_install_method(method: Optional[str], detail: Optional[str]) -> str:
    """Format detected local install method for display."""
    if method == "brew_formula":
        return f"Homebrew formula ({detail})" if detail else "Homebrew formula"
    if method == "brew_cask":
        return f"Homebrew cask ({detail})" if detail else "Homebrew cask"
    if method == "npm":
        return f"npm ({detail})" if detail else "npm"
    if method == "brew_npm":
        return (
            f"Homebrew prefix npm-global ({detail})"
            if detail
            else "Homebrew prefix npm-global"
        )
    if method == "system":
        return f"system package ({detail})" if detail else "system package"
    if method == "script":
        return "script"
    if method == "direct_download":
        return "direct download"
    if method:
        return method
    return "unknown"


# Install methods that are user-managed and never considered deprecated
_USER_MANAGED_METHODS = frozenset({"brew_formula", "brew_cask", "system"})

# Install methods that are considered deprecated when they don't match
# the configured install_type
_DEPRECATED_METHODS = frozenset({"npm", "brew_npm"})


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
    detected = install_info["method"]

    if not detected:
        return False

    if detected in _USER_MANAGED_METHODS:
        return False

    configured = tool_config.get("install_type")
    if not configured:
        return False

    if detected in _DEPRECATED_METHODS and detected != configured:
        return True

    return False


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

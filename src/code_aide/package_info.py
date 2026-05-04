"""Package version info lookup for system, brew, and FreeBSD pkg.

These helpers query external package managers to find the installed and
available versions of a tool. Each returns a :class:`PackageVersionInfo`
typed dict; failures are logged at DEBUG level and produce a partial result.
"""

import glob as globmod
import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from typing import Optional

from code_aide.console import command_exists
from code_aide.detection_types import PackageVersionInfo
from code_aide.install_types import (
    InstallMethod,
    InstallMethodInput,
    parse_install_method,
)

_logger = logging.getLogger(__name__)


def get_system_package_info(binary_path: str) -> PackageVersionInfo:
    """Get package version info for a system-installed binary."""
    result: PackageVersionInfo = {
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
        _logger.debug("qfile lookup failed for %s", binary_path, exc_info=True)
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
        _logger.debug("qlist/qatom lookup failed for %s", package, exc_info=True)

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
                _logger.debug(
                    "qatom version compare failed for %s/%s vs %s",
                    package,
                    version,
                    best_version,
                    exc_info=True,
                )

        if best_version:
            result["available_version"] = best_version
        if best_path:
            try:
                mtime = os.path.getmtime(best_path)
                result["available_date"] = datetime.fromtimestamp(
                    mtime, tz=timezone.utc
                ).strftime("%Y-%m-%d")
            except Exception:
                _logger.debug(
                    "ebuild mtime lookup failed for %s", best_path, exc_info=True
                )

    return result


def get_brew_package_info(
    method: InstallMethodInput, package_name: Optional[str]
) -> PackageVersionInfo:
    """Get package version info for a Homebrew-managed tool."""
    brew_method = parse_install_method(method)
    result: PackageVersionInfo = {
        "package": package_name,
        "installed_version": None,
        "available_version": None,
        "available_date": None,
        "outdated": None,
    }

    if (
        brew_method not in (InstallMethod.BREW_FORMULA, InstallMethod.BREW_CASK)
        or not package_name
    ):
        return result

    if not command_exists("brew"):
        return result

    command = ["brew", "info", "--json=v2"]
    if brew_method == InstallMethod.BREW_CASK:
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
        if brew_method == InstallMethod.BREW_FORMULA:
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
        _logger.debug("brew info lookup failed for %s", package_name, exc_info=True)
        return result

    return result


def get_pkg_package_info(
    package_name: str, repo: Optional[str] = None
) -> PackageVersionInfo:
    """Get package version info for a FreeBSD pkg-installed tool."""
    result: PackageVersionInfo = {
        "package": package_name,
        "installed_version": None,
        "available_version": None,
        "available_date": None,
        "outdated": None,
    }

    if not command_exists("pkg"):
        return result

    try:
        proc = subprocess.run(
            ["pkg", "query", "%v", package_name],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            result["installed_version"] = proc.stdout.strip().split("\n")[0]
    except Exception:
        _logger.debug("pkg query failed for %s", package_name, exc_info=True)

    try:
        rquery_cmd = ["pkg", "rquery"]
        if repo:
            rquery_cmd.extend(["-r", repo])
        rquery_cmd.extend(["%v", package_name])
        proc = subprocess.run(
            rquery_cmd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            result["available_version"] = proc.stdout.strip().split("\n")[0]
    except Exception:
        _logger.debug(
            "pkg rquery failed for %s (repo=%s)",
            package_name,
            repo,
            exc_info=True,
        )

    if result["installed_version"] and result["available_version"]:
        result["outdated"] = result["installed_version"] != result["available_version"]

    return result

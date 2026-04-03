"""Upgrade and remove operations for managed tools."""

import glob as globmod
import os
import shutil
import subprocess
import sys
from enum import Enum
from typing import Dict, List, TypedDict

from code_aide.constants import TOOLS
from code_aide.detection import (
    detect_install_method,
    format_install_method,
    is_deprecated_install,
)
from code_aide.package_managers import query_package_owner
from code_aide.install import (
    install_direct_download,
    install_tool,
    run_install_script,
    run_pkg_command,
)
from code_aide.install_types import (
    InstallMethod,
    InstallType,
    get_tool_install_type,
    install_method_from_type,
    parse_install_method,
)
from code_aide.console import error, info, run_command, success, warning
from code_aide.prereqs import is_tool_installed
from code_aide.status import get_tool_status


class UpgradeResult(Enum):
    """Possible outcomes from `upgrade_tool()`.

    Values:
    - `CHANGED`: The upgrade or migration changed the detected install state.
    - `UNCHANGED`: The upgrade command ran, but the detected install state did
      not change.
    - `FAILED`: The upgrade or migration failed.
    """

    CHANGED = "changed"
    UNCHANGED = "unchanged"
    FAILED = "failed"


class UpgradeSnapshot(TypedDict):
    """Install method and version captured before or after an upgrade."""

    method: InstallMethod | None
    detail: str | None
    version: str | None


def _get_upgrade_snapshot(
    tool_name: str, tool_config: Dict[str, str]
) -> UpgradeSnapshot:
    """Capture install method and version before/after a change."""
    install_info = detect_install_method(tool_name)
    status = get_tool_status(tool_name, tool_config)
    return {
        "method": install_info["method"],
        "detail": install_info["detail"],
        "version": status.get("version"),
    }


def _upgrade_result_from_snapshots(
    tool_config: Dict[str, str], before: UpgradeSnapshot, after: UpgradeSnapshot
) -> UpgradeResult:
    """Classify whether an upgrade actually changed the installed tool."""
    if before == after:
        version = after.get("version") or "unknown"
        info(
            f"{tool_config['name']} did not change after the upgrade attempt "
            f"(current version: {version})"
        )
        return UpgradeResult.UNCHANGED
    success(f"{tool_config['name']} upgraded successfully")
    return UpgradeResult.CHANGED


def _warn_duplicate_system_install(tool_name: str) -> None:
    """Warn if a duplicate system-packaged binary shadows or coexists."""
    tool_config = TOOLS[tool_name]
    command = tool_config["command"]

    # Find all instances of the command in PATH
    seen = set()
    paths = []
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(directory, command)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            real = os.path.realpath(candidate)
            if real not in seen:
                seen.add(real)
                paths.append(real)

    if len(paths) < 2:
        return

    system_prefixes = ("/opt/", "/usr/bin/", "/usr/sbin/", "/usr/local/bin/")
    for path in paths:
        if not any(path.startswith(p) for p in system_prefixes):
            continue
        package, remove_cmd = query_package_owner(path)
        if package and remove_cmd:
            warning(
                f"A system-packaged {command} is also installed at {path} "
                f"(package: {package})."
            )
            info(f"To remove it, run:  {remove_cmd}")
        else:
            warning(
                f"A system-packaged {command} is also installed at {path}. "
                "You may want to remove it with your package manager."
            )
        return


def _migrate_install_method(tool_name: str) -> UpgradeResult:
    """Migrate a tool from a deprecated install method to the configured one.

    Returns:
    - `UpgradeResult.CHANGED` when the tool is successfully migrated.
    - `UpgradeResult.FAILED` when removal, reinstall, or post-check verification
      fails.
    """
    tool_config = TOOLS[tool_name]
    install_info = detect_install_method(tool_name)
    old_label = format_install_method(install_info["method"], install_info["detail"])
    new_label = format_install_method(get_tool_install_type(tool_config), None)

    warning(
        f"{tool_config['name']} is installed via {old_label} "
        f"but the configured method is {new_label}."
    )
    info(f"Migrating {tool_config['name']} from {old_label} to {new_label}...")

    if not remove_tool(tool_name):
        error(
            f"Failed to remove old {old_label} install of {tool_config['name']}. "
            "Migration aborted."
        )
        return UpgradeResult.FAILED

    if not install_tool(tool_name, force=True):
        error(f"Failed to install {tool_config['name']} via {new_label}.")
        error(
            f"The old {old_label} install has been removed. "
            f"To recover, run: code-aide install {tool_name}"
        )
        return UpgradeResult.FAILED

    after = detect_install_method(tool_name)
    if parse_install_method(after["method"]) != install_method_from_type(
        get_tool_install_type(tool_config)
    ):
        detected_label = format_install_method(after["method"], after["detail"])
        error(
            f"Migration did not complete: {tool_config['name']} is still detected as "
            f"{detected_label}."
        )
        return UpgradeResult.FAILED

    success(f"{tool_config['name']} migrated from {old_label} to {new_label}")
    _warn_duplicate_system_install(tool_name)
    return UpgradeResult.CHANGED


def upgrade_tool(tool_name: str) -> UpgradeResult:
    """Upgrade a tool based on its configuration.

    Returns:
    - `UpgradeResult.CHANGED` when the installed tool changed version or install
      method.
    - `UpgradeResult.UNCHANGED` when the upgrade command ran but the detected
      install state did not change.
    - `UpgradeResult.FAILED` when the upgrade could not be completed.
    """
    tool_config = TOOLS.get(tool_name)
    if not tool_config:
        error(f"Unknown tool: {tool_name}")
        return UpgradeResult.FAILED

    if not is_tool_installed(tool_name):
        warning(f"{tool_config['name']} is not installed. Use 'install' command first.")
        return UpgradeResult.FAILED

    if is_deprecated_install(tool_name):
        return _migrate_install_method(tool_name)

    install_info = detect_install_method(tool_name)
    method = parse_install_method(install_info["method"])
    detail = install_info["detail"]
    before = _get_upgrade_snapshot(tool_name, tool_config)

    info(f"Upgrading {tool_config['name']} (installed via {method})...")

    try:
        if method == InstallMethod.BREW_FORMULA:
            run_command(["brew", "upgrade", detail], check=True, capture=False)

        elif method == InstallMethod.BREW_CASK:
            run_command(
                ["brew", "upgrade", "--cask", detail], check=True, capture=False
            )

        elif method in (InstallMethod.NPM, InstallMethod.BREW_NPM):
            npm_package = detail or tool_config.get("npm_package")
            if not npm_package:
                error(f"No npm package configured for {tool_config['name']}")
                return UpgradeResult.FAILED
            run_command(["npm", "install", "-g", f"{npm_package}@latest"], check=True)

        elif method == InstallMethod.SCRIPT:
            if get_tool_install_type(tool_config) == InstallType.DIRECT_DOWNLOAD:
                if not install_direct_download(tool_name, tool_config):
                    return UpgradeResult.FAILED
            else:
                install_url = tool_config["install_url"]
                expected_sha256 = tool_config.get("install_sha256")
                if run_install_script(
                    install_url, tool_config["name"], expected_sha256
                ):
                    pass
                else:
                    return UpgradeResult.FAILED

        elif method == InstallMethod.DIRECT_DOWNLOAD:
            if not install_direct_download(tool_name, tool_config):
                return UpgradeResult.FAILED

        elif method == InstallMethod.PKG:
            pkg_name = detail or tool_config.get("freebsd_port")
            if not pkg_name:
                error(f"No FreeBSD port configured for {tool_config['name']}")
                return UpgradeResult.FAILED
            pkg_repo = tool_config.get("freebsd_pkg_repo")
            run_pkg_command(
                ["sudo", "pkg", "install", "-y", "-f"],
                pkg_name,
                pkg_repo=pkg_repo,
                check=True,
                capture=False,
            )

        elif method == InstallMethod.SYSTEM:
            error(
                f"{tool_config['name']} is managed by the system package manager. "
                "Use your package manager to upgrade it."
            )
            return UpgradeResult.FAILED

        else:
            error(
                f"Don't know how to upgrade {tool_config['name']} "
                f"(install method: {method})"
            )
            return UpgradeResult.FAILED

        after = _get_upgrade_snapshot(tool_name, tool_config)
        return _upgrade_result_from_snapshots(tool_config, before, after)

    except subprocess.CalledProcessError as exc:
        error(f"Failed to upgrade {tool_config['name']}: {exc.stderr}")
        return UpgradeResult.FAILED
    except Exception as exc:
        error(f"Failed to upgrade {tool_config['name']}: {exc}")
        return UpgradeResult.FAILED


def remove_tool(tool_name: str) -> bool:
    """Remove a tool based on its configuration."""
    tool_config = TOOLS.get(tool_name)
    if not tool_config:
        error(f"Unknown tool: {tool_name}")
        return False

    if not is_tool_installed(tool_name):
        warning(f"{tool_config['name']} is not installed.")
        return True

    install_info = detect_install_method(tool_name)
    method = parse_install_method(install_info["method"])
    detail = install_info["detail"]

    info(f"Removing {tool_config['name']} (installed via {method})...")

    try:
        if method == InstallMethod.BREW_FORMULA:
            run_command(["brew", "uninstall", detail], check=True, capture=False)
            success(f"{tool_config['name']} removed successfully")

        elif method == InstallMethod.BREW_CASK:
            run_command(
                ["brew", "uninstall", "--cask", detail], check=True, capture=False
            )
            success(f"{tool_config['name']} removed successfully")

        elif method in (InstallMethod.NPM, InstallMethod.BREW_NPM):
            npm_package = detail or tool_config.get("npm_package")
            if not npm_package:
                error(f"No npm package configured for {tool_config['name']}")
                return False
            run_command(["npm", "uninstall", "-g", npm_package], check=True)
            success(f"{tool_config['name']} removed successfully")

        elif method == InstallMethod.SCRIPT:
            command = tool_config["command"]
            command_path = shutil.which(command)

            if command_path:
                try:
                    os.remove(command_path)
                    success(f"{tool_config['name']} removed successfully")
                except PermissionError:
                    try:
                        run_command(
                            ["sudo", "rm", command_path], check=True, capture=False
                        )
                        success(f"{tool_config['name']} removed successfully")
                    except subprocess.CalledProcessError as exc:
                        error(
                            f"Failed to remove {tool_config['name']}: {exc.stderr}. "
                            f"Please remove manually: {command_path}"
                        )
                        return False
                except Exception as exc:
                    error(f"Failed to remove {tool_config['name']}: {exc}")
                    return False
            else:
                warning(f"Could not find {command} binary to remove")
                return True

            if tool_name == "claude":
                claude_data = os.path.expanduser("~/.local/share/claude")
                if os.path.isdir(claude_data):
                    shutil.rmtree(claude_data)
                    info(f"Removed data directory: {claude_data}")

        elif method == InstallMethod.DIRECT_DOWNLOAD:
            bin_dir = os.path.expanduser(tool_config.get("bin_dir", "~/.local/bin"))
            removed_links = set()
            for link_name in tool_config.get("symlinks", {}):
                link_path = os.path.join(bin_dir, link_name)
                if os.path.lexists(link_path):
                    os.remove(link_path)
                    info(f"Removed symlink: {link_path}")
                    removed_links.add(link_path)

            command_path = shutil.which(tool_config["command"])
            if (
                command_path
                and command_path not in removed_links
                and os.path.lexists(command_path)
            ):
                os.remove(command_path)
                info(f"Removed: {command_path}")

            install_dir_template = tool_config.get("install_dir")
            if install_dir_template:
                if "{version}" in install_dir_template:
                    install_pattern = os.path.expanduser(
                        install_dir_template.replace("{version}", "*")
                    )
                    for install_path in sorted(globmod.glob(install_pattern)):
                        if os.path.isdir(install_path):
                            shutil.rmtree(install_path)
                            info(f"Removed: {install_path}")
                        elif os.path.lexists(install_path):
                            os.remove(install_path)
                            info(f"Removed: {install_path}")
                else:
                    install_path = os.path.expanduser(install_dir_template)
                    if os.path.isdir(install_path):
                        shutil.rmtree(install_path)
                        info(f"Removed: {install_path}")
                    elif os.path.lexists(install_path):
                        os.remove(install_path)
                        info(f"Removed: {install_path}")

            success(f"{tool_config['name']} removed successfully")

        elif method == InstallMethod.PKG:
            pkg_name = detail or tool_config.get("freebsd_port")
            if not pkg_name:
                error(f"No FreeBSD port configured for {tool_config['name']}")
                return False
            run_command(
                ["sudo", "pkg", "delete", "-y", pkg_name],
                check=True,
                capture=False,
            )
            success(f"{tool_config['name']} removed successfully")

        elif method == InstallMethod.SYSTEM:
            error(
                f"{tool_config['name']} is managed by the system package manager. "
                "Use your package manager to remove it."
            )
            return False

        else:
            error(
                f"Don't know how to remove {tool_config['name']} "
                f"(install method: {method})"
            )
            return False

        return True

    except subprocess.CalledProcessError as exc:
        error(f"Failed to remove {tool_config['name']}: {exc.stderr}")
        return False
    except Exception as exc:
        error(f"Failed to remove {tool_config['name']}: {exc}")
        return False


def validate_tools(tools: List[str]) -> None:
    """Validate that all tool names are valid."""
    invalid_tools = [tool for tool in tools if tool not in TOOLS]

    if invalid_tools:
        error(f"Invalid tool name(s): {', '.join(invalid_tools)}")
        available = ", ".join(TOOLS.keys())
        print(f"\nAvailable tools: {available}")
        sys.exit(1)

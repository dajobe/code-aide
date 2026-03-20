"""Upgrade and remove operations for managed tools."""

import glob as globmod
import os
import shutil
import subprocess
import sys
from enum import Enum
from typing import Dict, List

from code_aide.constants import TOOLS
from code_aide.detection import (
    detect_install_method,
    format_install_method,
    is_deprecated_install,
)
from code_aide.install import install_direct_download, install_tool, run_install_script
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


def _get_upgrade_snapshot(
    tool_name: str, tool_config: Dict[str, str]
) -> Dict[str, str]:
    """Capture install method and version before/after a change."""
    install_info = detect_install_method(tool_name)
    status = get_tool_status(tool_name, tool_config)
    return {
        "method": install_info["method"],
        "detail": install_info["detail"],
        "version": status.get("version"),
    }


def _upgrade_result_from_snapshots(
    tool_config: Dict[str, str], before: Dict[str, str], after: Dict[str, str]
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
    new_label = format_install_method(tool_config["install_type"], None)

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
    if after["method"] != tool_config["install_type"]:
        detected_label = format_install_method(after["method"], after["detail"])
        error(
            f"Migration did not complete: {tool_config['name']} is still detected as "
            f"{detected_label}."
        )
        return UpgradeResult.FAILED

    success(f"{tool_config['name']} migrated from {old_label} to {new_label}")
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
    method = install_info["method"]
    detail = install_info["detail"]
    before = _get_upgrade_snapshot(tool_name, tool_config)

    info(f"Upgrading {tool_config['name']} (installed via {method})...")

    try:
        if method == "brew_formula":
            run_command(["brew", "upgrade", detail], check=True, capture=False)

        elif method == "brew_cask":
            run_command(
                ["brew", "upgrade", "--cask", detail], check=True, capture=False
            )

        elif method in ("npm", "brew_npm"):
            npm_package = detail or tool_config.get("npm_package")
            if not npm_package:
                error(f"No npm package configured for {tool_config['name']}")
                return UpgradeResult.FAILED
            run_command(["npm", "install", "-g", f"{npm_package}@latest"], check=True)

        elif method == "script":
            if tool_config.get("install_type") == "direct_download":
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

        elif method == "direct_download":
            if not install_direct_download(tool_name, tool_config):
                return UpgradeResult.FAILED

        elif method == "system":
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
    method = install_info["method"]
    detail = install_info["detail"]

    info(f"Removing {tool_config['name']} (installed via {method})...")

    try:
        if method == "brew_formula":
            run_command(["brew", "uninstall", detail], check=True, capture=False)
            success(f"{tool_config['name']} removed successfully")

        elif method == "brew_cask":
            run_command(
                ["brew", "uninstall", "--cask", detail], check=True, capture=False
            )
            success(f"{tool_config['name']} removed successfully")

        elif method in ("npm", "brew_npm"):
            npm_package = detail or tool_config.get("npm_package")
            if not npm_package:
                error(f"No npm package configured for {tool_config['name']}")
                return False
            run_command(["npm", "uninstall", "-g", npm_package], check=True)
            success(f"{tool_config['name']} removed successfully")

        elif method == "script":
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

        elif method == "direct_download":
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

        elif method == "system":
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

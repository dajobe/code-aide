"""Upgrade and remove operations for managed tools."""

import os
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
from code_aide.install import install_tool
from code_aide.install_types import (
    InstallMethod,
    get_tool_install_type,
    install_method_from_type,
    parse_install_method,
)
from code_aide.operation_handlers import REMOVE_HANDLERS, UPGRADE_HANDLERS
from code_aide.console import (
    called_process_error_message,
    error,
    info,
    success,
    warning,
)
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

    if tool_config.get("self_updates"):
        info(
            f"{tool_config['name']} updates itself in the background when it runs; "
            f"launch '{tool_config['command']}' to allow it to update."
        )
        return UpgradeResult.UNCHANGED

    install_info = detect_install_method(tool_name)
    method = parse_install_method(install_info["method"])
    detail = install_info["detail"]
    before = _get_upgrade_snapshot(tool_name, tool_config)

    info(f"Upgrading {tool_config['name']} (installed via {method})...")

    handler = UPGRADE_HANDLERS.get(method) if method is not None else None
    if handler is None:
        error(
            f"Don't know how to upgrade {tool_config['name']} "
            f"(install method: {method})"
        )
        return UpgradeResult.FAILED

    try:
        if not handler(tool_name, tool_config, detail):
            return UpgradeResult.FAILED
        after = _get_upgrade_snapshot(tool_name, tool_config)
        return _upgrade_result_from_snapshots(tool_config, before, after)

    except subprocess.CalledProcessError as exc:
        error(
            f"Failed to upgrade {tool_config['name']}: "
            f"{called_process_error_message(exc)}"
        )
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

    handler = REMOVE_HANDLERS.get(method) if method is not None else None
    if handler is None:
        error(
            f"Don't know how to remove {tool_config['name']} "
            f"(install method: {method})"
        )
        return False

    try:
        return handler(tool_name, tool_config, detail)
    except subprocess.CalledProcessError as exc:
        error(
            f"Failed to remove {tool_config['name']}: "
            f"{called_process_error_message(exc)}"
        )
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

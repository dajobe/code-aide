"""Upgrade and remove operations for managed tools."""

import fnmatch
import os
import shutil
import subprocess
import sys
from enum import Enum
from typing import Dict, List, Optional, TypedDict

from code_aide.app_bundle import app_is_running, is_app_bundle_tool
from code_aide.constants import TOOLS
from code_aide.detection import (
    detect_install_method,
    format_install_method,
    is_deprecated_install,
)
from code_aide.package_managers import query_package_owner
from code_aide.path_copies import find_command_copies, removal_hint
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


def warn_service_restart(tool_config: Dict) -> None:
    """Warn when a background service keeps running the previous version.

    code-aide switches the command but never restarts a service, since that
    can interrupt work in progress.
    """
    service_files = [
        os.path.expanduser(p) for p in tool_config.get("service_files", [])
    ]
    if any(os.path.exists(path) for path in service_files):
        warning(tool_config["service_restart_hint"])


def _warn_duplicate_installs(tool_name: str) -> None:
    """Warn about other copies of the command that coexist on PATH."""
    copies = find_command_copies(tool_name)
    if len(copies) < 2:
        return

    command = TOOLS[tool_name]["command"]
    active = copies[0]
    for copy in copies[1:]:
        label = format_install_method(copy.install["method"], copy.install["detail"])
        hint = removal_hint(copy)
        if (
            hint is None
            and parse_install_method(copy.install["method"]) == InstallMethod.SYSTEM
        ):
            _package, hint = query_package_owner(copy.real_path)
        warning(
            f"Another {command} is installed at {copy.path} ({label}); "
            f"{active.path} comes first on PATH."
        )
        if hint:
            info(f"To remove it, run:  {hint}")


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

    if not remove_tool(tool_name, warn_remaining=False):
        error(
            f"Failed to remove old {old_label} install of {tool_config['name']}. "
            "Migration aborted."
        )
        return UpgradeResult.FAILED

    if not install_tool(tool_name, force=True, report_existing=False):
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
    warn_service_restart(tool_config)
    _warn_duplicate_installs(tool_name)
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
        _warn_duplicate_installs(tool_name)
        result = _upgrade_result_from_snapshots(tool_config, before, after)
        if result == UpgradeResult.CHANGED:
            warn_service_restart(tool_config)
        return result

    except subprocess.CalledProcessError as exc:
        error(
            f"Failed to upgrade {tool_config['name']}: "
            f"{called_process_error_message(exc)}"
        )
        return UpgradeResult.FAILED
    except Exception as exc:
        error(f"Failed to upgrade {tool_config['name']}: {exc}")
        return UpgradeResult.FAILED


def remove_tool(tool_name: str, warn_remaining: bool = True) -> bool:
    """Remove a tool based on its configuration.

    With warn_remaining, reports copies of the command still on PATH
    afterwards (for example a second npm global install).
    """
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
        removed = handler(tool_name, tool_config, detail)
        if removed and warn_remaining:
            for copy in find_command_copies(tool_name):
                warning(
                    f"{tool_config['command']} is still on PATH at {copy.path} "
                    f"({format_install_method(copy.install['method'], copy.install['detail'])})."
                )
                hint = removal_hint(copy)
                if hint:
                    info(f"To remove it, run:  {hint}")
        return removed
    except subprocess.CalledProcessError as exc:
        error(
            f"Failed to remove {tool_config['name']}: "
            f"{called_process_error_message(exc)}"
        )
        return False
    except Exception as exc:
        error(f"Failed to remove {tool_config['name']}: {exc}")
        return False


def clean_tool_versions(tool_name: str, dryrun: bool = False) -> Optional[List[str]]:
    """Remove stale version directories for a direct-download tool.

    Keeps the directory the tool's symlinks currently point at. Returns
    the list of removed (or, with dryrun, removable) directory paths,
    or None when the tool has no versioned install layout.
    """
    tool_config = TOOLS[tool_name]
    install_dir_template = tool_config.get("install_dir", "")
    if not install_dir_template or "{version}" not in install_dir_template:
        return None
    if tool_config.get("self_pruning_versions"):
        info(
            f"{tool_config['name']} prunes its own old versions; "
            "code-aide leaves them alone"
        )
        return None
    if is_app_bundle_tool(tool_config) and app_is_running(tool_config) is not False:
        warning(
            f"{tool_config['name']} is running (or could not be checked); "
            "not removing old versions"
        )
        return []

    expanded = os.path.expanduser(install_dir_template)
    parent = os.path.dirname(expanded)
    if not parent or not os.path.isdir(parent):
        info(f"No install directory for {tool_config['name']}; nothing to clean")
        return []

    # Only consider directories matching the versioned template shape.
    pattern = os.path.basename(expanded).replace("{version}", "*")

    # Never remove the version the symlinks currently point at.
    current_dirs = set()
    if is_app_bundle_tool(tool_config):
        link_paths = [os.path.expanduser(tool_config["app_link"])]
    else:
        bin_dir = os.path.expanduser(tool_config.get("bin_dir", ""))
        link_paths = [
            os.path.join(bin_dir, name) for name in tool_config.get("symlinks", {})
        ]
    for link_path in link_paths:
        if os.path.islink(link_path):
            current_dirs.add(os.path.dirname(os.path.realpath(link_path)))

    if not current_dirs:
        warning(
            f"Could not determine the current version directory of "
            f"{tool_config['name']}; not removing anything"
        )
        return []

    stale = []
    for entry in sorted(os.listdir(parent)):
        full = os.path.join(parent, entry)
        if not os.path.isdir(full) or os.path.islink(full):
            continue
        if not fnmatch.fnmatch(entry, pattern):
            continue
        if full in current_dirs or os.path.realpath(full) in current_dirs:
            continue
        stale.append(full)

    if not stale:
        info(f"No stale version directories for {tool_config['name']}")
        return []

    if dryrun:
        for path in stale:
            info(f"[DRYRUN] Would remove stale version directory: {path}")
        return stale

    for path in stale:
        shutil.rmtree(path)
        info(f"Removed stale version directory: {path}")
    return stale


def validate_tools(tools: List[str]) -> None:
    """Validate that all tool names are valid."""
    invalid_tools = [tool for tool in tools if tool not in TOOLS]

    if invalid_tools:
        error(f"Invalid tool name(s): {', '.join(invalid_tools)}")
        available = ", ".join(TOOLS.keys())
        print(f"\nAvailable tools: {available}")
        sys.exit(1)

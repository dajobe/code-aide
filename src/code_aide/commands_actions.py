"""Mutating CLI commands: install, upgrade, remove, update-versions."""

import argparse
import sys
from typing import Any, Dict, List

from code_aide.constants import TOOLS
from code_aide.detection import (
    detect_install_method,
    get_brew_package_info,
    is_deprecated_install,
)
from code_aide.install import install_tool
from code_aide.console import error, info, success, warning
from code_aide.operations import (
    UpgradeResult,
    remove_tool,
    upgrade_tool,
    validate_tools,
)
from code_aide.prereqs import (
    check_path_directories,
    check_prerequisites,
    is_tool_installed,
)
from code_aide.status import get_tool_status
from code_aide.versions import (
    apply_sha256_updates,
    check_npm_tool,
    check_script_tool,
    normalize_version,
    print_check_results_table,
    status_version_matches_latest,
)
from code_aide.config import (
    load_bundled_tools,
    load_versions_cache,
    merge_cached_versions,
    save_updated_versions,
)


def cmd_install(args: argparse.Namespace) -> None:
    """Handle install command."""
    dryrun = getattr(args, "dryrun", False)

    if args.tools:
        tools_to_install = args.tools
        if dryrun:
            info(f"[DRYRUN] Checking specified tools: {', '.join(tools_to_install)}")
        else:
            info(f"Installing specified tools: {', '.join(tools_to_install)}")
    else:
        tools_to_install = [
            name
            for name, config in TOOLS.items()
            if config.get("default_install", True)
        ]
        if dryrun:
            info(f"[DRYRUN] Checking default tools: {', '.join(tools_to_install)}")
        else:
            info(
                "No tools specified, installing default tools: "
                f"{', '.join(tools_to_install)}"
            )

    validate_tools(tools_to_install)

    if not dryrun:
        check_prerequisites(
            tools_to_install, install_prereqs=args.install_prerequisites
        )

    installed = []
    failed = []

    for tool in tools_to_install:
        print()
        if dryrun:
            info(f"=== Checking {tool} ===")
        else:
            info(f"=== Installing {tool} ===")

        if install_tool(tool, dryrun=dryrun):
            installed.append(tool)
        else:
            failed.append(tool)

    print()
    print("=" * 42)
    if dryrun:
        info("Verification Summary")
    else:
        info("Installation Summary")
    print("=" * 42)

    if installed:
        if dryrun:
            success(f"Verification passed: {', '.join(installed)}")
        else:
            success(f"Successfully installed: {', '.join(installed)}")

    if failed:
        if dryrun:
            error(f"Verification failed: {', '.join(failed)}")
        else:
            error(f"Failed to install: {', '.join(failed)}")
        sys.exit(1)

    if dryrun:
        print()
        success("All verifications completed successfully!")
    else:
        print()
        info("Next steps:")
        for tool in installed:
            tool_config = TOOLS.get(tool)
            if tool_config:
                print(f"  {tool_config['next_steps']}")

        print()
        check_path_directories(installed)
        success("All installations completed successfully!")


def cmd_upgrade(args: argparse.Namespace) -> None:
    """Handle upgrade command."""
    if args.tools:
        tools_to_upgrade = args.tools
        info(f"Upgrading specified tools: {', '.join(tools_to_upgrade)}")
    else:
        tools_to_upgrade = []
        for name, config in TOOLS.items():
            if not is_tool_installed(name):
                continue
            if is_deprecated_install(name):
                if name not in tools_to_upgrade:
                    tools_to_upgrade.append(name)
                continue
            latest = config.get("latest_version")
            if not latest:
                continue
            install_info = detect_install_method(name)
            if install_info["method"] in ("brew_formula", "brew_cask"):
                pkg_info = get_brew_package_info(
                    install_info["method"], install_info["detail"]
                )
                if pkg_info.get("outdated") is False:
                    continue
            status = get_tool_status(name, config)
            if status["version"] and status_version_matches_latest(
                status["version"], latest
            ):
                continue
            tools_to_upgrade.append(name)
        if tools_to_upgrade:
            info(f"Upgrading out-of-date tools: {', '.join(tools_to_upgrade)}")
        else:
            info("All installed tools are up to date")
            return

    validate_tools(tools_to_upgrade)

    updated = []
    unchanged = []
    failed = []
    skipped = []

    for tool in tools_to_upgrade:
        print()
        info(f"=== Upgrading {tool} ===")

        if not is_tool_installed(tool):
            skipped.append(tool)
            continue

        result = upgrade_tool(tool)
        if result == UpgradeResult.CHANGED:
            updated.append(tool)
        elif result == UpgradeResult.UNCHANGED:
            unchanged.append(tool)
        else:
            failed.append(tool)

    print()
    print("=" * 42)
    info("Upgrade Summary")
    print("=" * 42)

    if updated:
        success(f"Successfully updated: {', '.join(updated)}")

    if unchanged:
        info(f"No package-manager change: {', '.join(unchanged)}")

    if skipped:
        warning(f"Skipped (not installed): {', '.join(skipped)}")

    if failed:
        error(f"Failed to upgrade: {', '.join(failed)}")
        sys.exit(1)

    if updated:
        success("All upgrades completed successfully!")
    elif unchanged and not updated and not failed:
        info("No tools changed version during the upgrade attempt")
    elif skipped and not updated:
        info(
            "No tools were upgraded (all were either not installed or already up to date)"
        )


def cmd_remove(args: argparse.Namespace) -> None:
    """Handle remove command."""
    if args.tools:
        tools_to_remove = args.tools
        info(f"Removing specified tools: {', '.join(tools_to_remove)}")
    else:
        tools_to_remove = list(TOOLS.keys())
        info(f"No tools specified, removing all: {', '.join(tools_to_remove)}")

    validate_tools(tools_to_remove)

    removed = []
    failed = []
    skipped = []

    for tool in tools_to_remove:
        print()
        info(f"=== Removing {tool} ===")

        if not is_tool_installed(tool):
            skipped.append(tool)
            continue

        if remove_tool(tool):
            removed.append(tool)
        else:
            failed.append(tool)

    print()
    print("=" * 42)
    info("Removal Summary")
    print("=" * 42)

    if removed:
        success(f"Successfully removed: {', '.join(removed)}")

    if skipped:
        warning(f"Skipped (not installed): {', '.join(skipped)}")

    if failed:
        error(f"Failed to remove: {', '.join(failed)}")
        sys.exit(1)

    if removed:
        success("All removals completed successfully!")
    elif skipped and not removed:
        info("No tools were removed (all were not installed)")


def cmd_update_versions(args: argparse.Namespace) -> None:
    """Handle update-versions command: check upstream for latest tool versions."""
    bundled = load_bundled_tools()
    tools = bundled.get("tools", {})
    merge_cached_versions(tools, load_versions_cache())

    config: Dict[str, Any] = {"tools": tools}

    if args.tools:
        invalid = [tool for tool in args.tools if tool not in tools]
        if invalid:
            error(f"Unknown tool(s): {', '.join(invalid)}")
            print(f"Available: {', '.join(tools.keys())}", file=sys.stderr)
            sys.exit(1)
        tool_names = args.tools
    else:
        tool_names = list(tools.keys())

    print(f"Checking {len(tool_names)} tool(s) for updates...")

    results: List[Dict[str, Any]] = []
    for name in tool_names:
        tool_config = tools[name]
        install_type = tool_config["install_type"]

        if install_type == "npm":
            results.append(check_npm_tool(name, tool_config, args.verbose))
        elif install_type in ("script", "direct_download"):
            results.append(check_script_tool(name, tool_config, args.verbose))
        else:
            results.append(
                {
                    "tool": name,
                    "type": install_type,
                    "version": "-",
                    "date": "-",
                    "status": f"unknown type: {install_type}",
                    "update": None,
                }
            )

    print_check_results_table(results, verbose=args.verbose)

    version_info_changed = False
    for result in results:
        if result["status"] == "error":
            continue
        tool_name = result["tool"]
        version = result.get("version", "-")
        date = result.get("date", "-")
        tool_entry = config["tools"][tool_name]
        if version and version != "-":
            normalized = normalize_version(version)
            if tool_entry.get("latest_version") != normalized:
                tool_entry["latest_version"] = normalized
                version_info_changed = True
        if date and date != "-":
            if tool_entry.get("latest_date") != date:
                tool_entry["latest_date"] = date
                version_info_changed = True

    def _save(tools: dict) -> str:
        """Save versions to user cache. Returns description."""
        save_updated_versions(tools)
        return "~/.config/code-aide/versions.json"

    updates = [result for result in results if result["update"]]
    if not updates:
        if version_info_changed and not args.dryrun:
            dest = _save(config["tools"])
            print(f"Updated latest version info in {dest}.")
        if version_info_changed:
            print(
                "No installer checksum updates required "
                "(latest version metadata was refreshed)."
            )
        else:
            print("No upstream config changes detected.")
        print(
            "Note: 'update-versions' checks upstream metadata, not your installed "
            "binary versions. Use 'code-aide status' and 'code-aide upgrade' "
            "for local installs."
        )
        return

    print(f"{len(updates)} update(s) available:")
    for result in updates:
        print(f"  {result['tool']}: SHA256 changed")

    if args.dryrun:
        print("\nDry run mode - no changes written.")
        return

    if not args.yes:
        try:
            answer = input("\nApply these updates? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return
        if answer not in ("y", "yes"):
            if version_info_changed:
                dest = _save(config["tools"])
                print(f"Updated latest version info in {dest}.")
            else:
                print("No changes made.")
            return

    updated = apply_sha256_updates(config, results)
    dest = _save(config["tools"])

    print(f"\nUpdated {len(updated)} tool(s) in {dest}:")
    for name in updated:
        print(f"  {name}")
    if version_info_changed:
        print("Also updated latest version info for checked tools.")
    print("\nRun 'code-aide status' to see current state.")

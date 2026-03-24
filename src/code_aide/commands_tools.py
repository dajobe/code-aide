"""Read-only CLI commands: list and status."""

from __future__ import annotations

import argparse
import platform
import shutil
from typing import List

from code_aide.constants import Colors, PACKAGE_MANAGERS, TOOLS
from code_aide.detection import (
    format_install_method,
    format_migration_warning,
    detect_install_method,
)
from code_aide.console import command_exists, info, warning
from code_aide.install_types import (
    InstallMethod,
    parse_install_method,
    parse_install_type,
)
from code_aide.prereqs import detect_package_manager, is_tool_installed
from code_aide.detection import is_freebsd
from code_aide.status import (
    print_brew_version_status,
    print_pkg_version_status,
    print_system_version_status,
    ToolUpgradeEvaluator,
    UpgradeDecision,
    VersionDisplayState,
)
from code_aide.versions import (
    extract_version_from_string,
)


def cmd_list(args: argparse.Namespace) -> None:
    """Handle list command."""
    print("Available AI Coding CLI Tools:")
    print("=" * 70)
    print()

    for tool_name, tool_config in TOOLS.items():
        installed = is_tool_installed(tool_name)
        status = (
            f"{Colors.GREEN}✓ Installed{Colors.NC}"
            if installed
            else f"{Colors.RED}✗ Not installed{Colors.NC}"
        )

        print(f"{Colors.BLUE}{tool_config['name']}{Colors.NC}")
        print(f"  Command:      {tool_config['command']}")
        print(f"  Status:       {status}")
        install_type = parse_install_type(tool_config["install_type"])
        managed_by = install_type.value if install_type else tool_config["install_type"]
        print(f"  Managed by:   {managed_by} (code-aide)")

        if installed:
            tool_path = shutil.which(tool_config["command"])
            print(f"  Location:     {tool_path}")
            install_info = detect_install_method(tool_name)
            print(
                "  Installed via: "
                f"{format_install_method(install_info['method'], install_info['detail'])}"
            )
            migration_msg = format_migration_warning(tool_name)
            if migration_msg:
                warning(f"  {migration_msg}")

        if tool_config.get("min_node_version"):
            print(f"  Requires:     Node.js v{tool_config['min_node_version']}+")

        if is_freebsd() and not tool_config.get("freebsd_port"):
            print("  Note:         Not available on FreeBSD")

        if not tool_config.get("default_install", True):
            print(
                "  Note:         Opt-in only "
                f"(specify 'code-aide install {tool_name}')"
            )

        if tool_config.get("docs_url"):
            print(f"  Docs:         {tool_config['docs_url']}")

        print()

    print("=" * 70)
    info("System Information:")
    print(f"  Platform: {platform.system()}")

    if command_exists("npm"):
        try:
            from code_aide.console import run_command

            npm_version = run_command(["npm", "--version"]).stdout.strip()
            print(f"  npm:      {npm_version}")
        except Exception:
            pass

    if command_exists("node"):
        try:
            from code_aide.console import run_command

            node_version = run_command(["node", "--version"]).stdout.strip()
            print(f"  Node.js:  {node_version}")
        except Exception:
            pass

    pkg_mgr = detect_package_manager()
    if pkg_mgr:
        print(
            f"  Package manager: {PACKAGE_MANAGERS[pkg_mgr]['description']} ({pkg_mgr})"
        )


def _short_install_method(method: str | None) -> str:
    """Return a short label for an install method."""
    labels = {
        InstallMethod.BREW_FORMULA: "brew",
        InstallMethod.BREW_CASK: "cask",
        InstallMethod.NPM: "npm",
        InstallMethod.BREW_NPM: "brew-npm",
        InstallMethod.SYSTEM: "system",
        InstallMethod.PKG: "pkg",
        InstallMethod.SCRIPT: "script",
        InstallMethod.DIRECT_DOWNLOAD: "download",
    }
    install_method = parse_install_method(method)
    if install_method is None:
        return str(method or "unknown")
    return labels.get(install_method, str(install_method))


def _compact_version_status(
    installed_version: str | None, version_state: VersionDisplayState
) -> tuple[str, str]:
    """Return (version_str, status_indicator) for compact display."""
    if not installed_version:
        return ("", "")
    ver = extract_version_from_string(installed_version) or installed_version
    if version_state == VersionDisplayState.UP_TO_DATE:
        return (ver, f"{Colors.GREEN}ok{Colors.NC}")
    if version_state == VersionDisplayState.OUTDATED:
        return (ver, f"{Colors.YELLOW}old{Colors.NC}")
    return (ver, "")


def _generic_version_annotation(
    installed_version: str, latest_version: str | None
) -> str:
    """Return the generic version line for non-package-managed status."""
    if not latest_version:
        return f"  Version:      {installed_version}"

    return (
        f"  Version:      {installed_version} "
        f"{Colors.YELLOW}(latest: {latest_version}){Colors.NC}"
    )


def cmd_status_compact() -> None:
    """Show compact one-line-per-tool status."""
    rows: list[tuple[str, str, str, str, str]] = []
    for tool_name, tool_config in TOOLS.items():
        name = tool_config["command"]
        assessment = ToolUpgradeEvaluator(tool_name, tool_config).evaluate()
        status = assessment.status

        if not status["installed"]:
            opt_in = not tool_config.get("default_install", True)
            if opt_in:
                state = "opt-in"
            else:
                state = f"{Colors.RED}missing{Colors.NC}"
            rows.append((name, state, "", "", ""))
            continue

        tool_path = shutil.which(tool_config["command"]) or ""
        method = _short_install_method(assessment.install_method)
        ver, ver_status = _compact_version_status(
            assessment.installed_version, assessment.version_state
        )

        state = f"{Colors.GREEN}ok{Colors.NC}"
        if ver_status:
            state = ver_status

        rows.append((name, state, ver, method, tool_path))

    # Calculate column widths (ignoring ANSI escape codes)
    import re

    def visible_len(s: str) -> int:
        return len(re.sub(r"\033\[[^m]*m", "", s))

    headers = ("TOOL", "STATE", "VERSION", "VIA", "PATH")
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], visible_len(cell))

    def fmt_row(row: tuple[str, ...]) -> str:
        parts = []
        for i, cell in enumerate(row):
            pad = widths[i] - visible_len(cell)
            parts.append(cell + " " * pad)
        return "  ".join(parts).rstrip()

    print(fmt_row(headers))
    for row in rows:
        print(fmt_row(row))


def cmd_status(args: argparse.Namespace) -> None:
    """Handle status command."""
    if getattr(args, "compact", False):
        cmd_status_compact()
        return
    print("AI Coding CLI Tools Status:")
    print("=" * 70)
    print()

    outdated_count = 0
    outdated_tools: List[str] = []
    migration_count = 0

    for tool_name, tool_config in TOOLS.items():
        print(f"{Colors.BLUE}{tool_config['name']}{Colors.NC}")

        tool_path = shutil.which(tool_config["command"])
        assessment = ToolUpgradeEvaluator(
            tool_name, tool_config, tool_path=tool_path
        ).evaluate()
        status = assessment.status

        if not status["installed"]:
            print(f"  Status:       {Colors.RED}✗ Not installed{Colors.NC}")
        else:
            print(f"  Status:       {Colors.GREEN}✓ Installed{Colors.NC}")

            if status["version"]:
                if (
                    assessment.install_method == InstallMethod.SYSTEM
                    and tool_path
                    and assessment.package_info
                ):
                    print_system_version_status(
                        status["version"],
                        assessment.latest_version,
                        assessment.package_info,
                    )
                elif assessment.install_method == InstallMethod.PKG:
                    if assessment.package_info and assessment.package_info.get(
                        "available_version"
                    ):
                        print_pkg_version_status(
                            status["version"],
                            assessment.latest_version,
                            assessment.package_info,
                            repo=tool_config.get("freebsd_pkg_repo"),
                        )
                    elif assessment.latest_version:
                        if assessment.version_state == VersionDisplayState.UP_TO_DATE:
                            print(
                                f"  Version:      {status['version']} "
                                f"{Colors.GREEN}(up to date){Colors.NC}"
                            )
                        else:
                            print(
                                _generic_version_annotation(
                                    status["version"], assessment.latest_version
                                )
                            )
                    else:
                        print(f"  Version:      {status['version']}")
                elif assessment.install_method in (
                    InstallMethod.BREW_FORMULA,
                    InstallMethod.BREW_CASK,
                ):
                    if assessment.package_info and assessment.package_info.get(
                        "available_version"
                    ):
                        print_brew_version_status(
                            status["version"],
                            assessment.latest_version,
                            assessment.package_info,
                        )
                    elif assessment.latest_version:
                        if assessment.version_state == VersionDisplayState.UP_TO_DATE:
                            print(
                                f"  Version:      {status['version']} "
                                f"{Colors.GREEN}(up to date){Colors.NC}"
                            )
                        else:
                            print(
                                _generic_version_annotation(
                                    status["version"], assessment.latest_version
                                )
                            )
                    else:
                        print(f"  Version:      {status['version']}")
                elif assessment.latest_version:
                    if assessment.version_state == VersionDisplayState.UP_TO_DATE:
                        print(
                            f"  Version:      {status['version']} "
                            f"{Colors.GREEN}(up to date){Colors.NC}"
                        )
                    else:
                        print(
                            _generic_version_annotation(
                                status["version"], assessment.latest_version
                            )
                        )
                else:
                    print(f"  Version:      {status['version']}")

                if assessment.decision == UpgradeDecision.UPGRADE:
                    outdated_count += 1
                    outdated_tools.append(tool_name)

            if tool_path:
                print(f"  Location:     {tool_path}")
                print(
                    "  Installed via: "
                    f"{format_install_method(assessment.install_method, assessment.install_detail)}"
                )
                if assessment.decision == UpgradeDecision.MIGRATION:
                    migration_count += 1
                    migration_msg = format_migration_warning(tool_name)
                    if migration_msg:
                        warning(f"  {migration_msg}")

            if status["user"]:
                print(f"  User:         {status['user']}")

            if status["usage"]:
                print(f"  Usage:        {status['usage']}")

            if status["errors"]:
                for err_msg in status["errors"]:
                    warning(f"  {err_msg}")

        print()

    if outdated_count > 0:
        names = ", ".join(outdated_tools)
        print(
            f"{Colors.YELLOW}{outdated_count} tool(s) can be upgraded with "
            f"'code-aide upgrade': {names}.{Colors.NC}"
        )
    if migration_count > 0:
        print(
            f"{Colors.YELLOW}{migration_count} tool(s) need migration to a "
            f"new install method. Run 'code-aide upgrade' to migrate.{Colors.NC}"
        )

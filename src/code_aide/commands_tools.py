"""Read-only CLI commands: list and status."""

from __future__ import annotations

import argparse
import logging
import platform
import shutil
from typing import List

from code_aide.app_bundle import is_app_bundle_tool, tool_location
from code_aide.config import ensure_versions_cache
from code_aide.constants import Colors, TOOLS
from code_aide.detection import (
    format_install_method,
    format_migration_warning,
    detect_install_method,
    is_brew_cask_installed,
)
from code_aide.console import command_exists, info, warning
from code_aide.install_types import (
    InstallMethod,
    parse_install_method,
    parse_install_type,
)
from code_aide.package_managers import (
    detect_package_manager as _detect_package_manager,
)
from code_aide.path_copies import removal_hint, shadowed_copies
from code_aide.prereqs import is_tool_installed
from code_aide.tool_groups import linked_version_mismatches
from code_aide.detection import is_freebsd
from code_aide.status import (
    print_brew_version_status,
    print_pkg_version_status,
    print_system_version_status,
    ToolUpgradeAssessment,
    ToolUpgradeEvaluator,
    UpgradeDecision,
    VersionDisplayState,
)
from code_aide.versions import (
    extract_version_from_string,
)

_logger = logging.getLogger(__name__)


def _locate(tool_config: dict) -> str | None:
    """Return the tool's app bundle or the command found on PATH."""
    if is_app_bundle_tool(tool_config):
        return tool_location(tool_config)
    return shutil.which(tool_config["command"])


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
        if is_app_bundle_tool(tool_config):
            print(f"  App:          {tool_config['app_link']}")
        else:
            print(f"  Command:      {tool_config['command']}")
        print(f"  Status:       {status}")
        install_type = parse_install_type(tool_config["install_type"])
        managed_by = install_type.value if install_type else tool_config["install_type"]
        print(f"  Managed by:   {managed_by} (code-aide)")

        if installed:
            tool_path = _locate(tool_config)
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

    from code_aide.console import run_command

    if command_exists("npm"):
        try:
            npm_version = run_command(["npm", "--version"]).stdout.strip()
            print(f"  npm:      {npm_version}")
        except Exception:
            _logger.debug("Failed to read npm --version", exc_info=True)

    if command_exists("node"):
        try:
            node_version = run_command(["node", "--version"]).stdout.strip()
            print(f"  Node.js:  {node_version}")
        except Exception:
            _logger.debug("Failed to read node --version", exc_info=True)

    pkg_mgr = _detect_package_manager()
    if pkg_mgr:
        print(f"  Package manager: {pkg_mgr.description} ({pkg_mgr.detect_command})")


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
        InstallMethod.APP_BUNDLE: "app",
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
    return (ver, "?")


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


def _print_version_status(
    assessment: ToolUpgradeAssessment,
    status_version: str,
    tool_path: str | None,
    tool_config: dict,
) -> None:
    """Print the long-form version line for one installed tool."""
    package_info = assessment.package_info
    if assessment.install_method == InstallMethod.SYSTEM and tool_path and package_info:
        print_system_version_status(
            status_version, assessment.latest_version, package_info
        )
        return

    if assessment.install_method == InstallMethod.PKG:
        if package_info and package_info.get("available_version"):
            print_pkg_version_status(
                status_version,
                assessment.latest_version,
                package_info,
                repo=tool_config.get("freebsd_pkg_repo"),
            )
            return
    elif assessment.install_method in (
        InstallMethod.BREW_FORMULA,
        InstallMethod.BREW_CASK,
    ):
        if package_info and package_info.get("available_version"):
            print_brew_version_status(
                status_version, assessment.latest_version, package_info
            )
            return

    if (
        assessment.latest_version
        and assessment.version_state == VersionDisplayState.UP_TO_DATE
    ):
        print(
            f"  Version:      {status_version} "
            f"{Colors.GREEN}(up to date){Colors.NC}"
        )
    else:
        print(_generic_version_annotation(status_version, assessment.latest_version))


def cmd_status_compact() -> None:
    """Show compact one-line-per-tool status."""
    ensure_versions_cache(TOOLS)
    rows: list[tuple[str, str, str, str, str]] = []
    failed_checks: list[tuple[str, str]] = []
    for tool_name, tool_config in TOOLS.items():
        assessment = ToolUpgradeEvaluator(tool_name, tool_config).evaluate()
        status = assessment.status

        if not status["installed"]:
            opt_in = not tool_config.get("default_install", True)
            if opt_in:
                state = "opt-in"
            else:
                state = f"{Colors.RED}missing{Colors.NC}"
            cask = tool_config.get("brew_cask")
            if cask and is_brew_cask_installed(cask):
                rows.append((tool_name, state, "", "cask", "desktop app only, no CLI"))
            else:
                rows.append((tool_name, state, "", "", ""))
            continue

        tool_path = _locate(tool_config) or ""
        method = _short_install_method(assessment.install_method)
        ver, ver_status = _compact_version_status(
            assessment.installed_version, assessment.version_state
        )

        state = ver_status if ver_status else "?"
        version_error = status.get("version_error")
        if not status["version"] and version_error:
            state = f"{Colors.RED}failed{Colors.NC}"
            failed_checks.append((tool_name, version_error))
        shadowed = len(shadowed_copies(tool_name))
        if shadowed:
            tool_path += f" {Colors.YELLOW}(+{shadowed} shadowed){Colors.NC}"

        rows.append((tool_name, state, ver, method, tool_path))

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
    for tool_name, version_error in failed_checks:
        warning(
            f"{tool_name}: version check failed ({version_error}); "
            f"try 'code-aide upgrade {tool_name}' to reinstall it."
        )
    for message in linked_version_mismatches():
        warning(message)


def cmd_status(args: argparse.Namespace) -> None:
    """Handle status command."""
    if not getattr(args, "long", False):
        cmd_status_compact()
        return
    ensure_versions_cache(TOOLS)
    print("AI Coding CLI Tools Status:")
    print("=" * 70)
    print()

    outdated_count = 0
    outdated_tools: List[str] = []
    migration_count = 0

    for tool_name, tool_config in TOOLS.items():
        print(f"{Colors.BLUE}{tool_config['name']}{Colors.NC}")

        tool_path = _locate(tool_config)
        assessment = ToolUpgradeEvaluator(
            tool_name, tool_config, tool_path=tool_path
        ).evaluate()
        status = assessment.status

        if not status["installed"]:
            print(f"  Status:       {Colors.RED}✗ Not installed{Colors.NC}")
            cask = tool_config.get("brew_cask")
            if cask and is_brew_cask_installed(cask):
                info(
                    f"  Desktop app installed via Homebrew cask ({cask}) without "
                    f"the {tool_config['command']} command."
                )
                if tool_config.get("desktop_cli_hint"):
                    info(f"  {tool_config['desktop_cli_hint']}")
        else:
            print(f"  Status:       {Colors.GREEN}✓ Installed{Colors.NC}")

            if not status["version"] and status.get("version_error"):
                warning(
                    f"  Version check failed: {status['version_error']}. "
                    f"Try 'code-aide upgrade {tool_name}' to reinstall it."
                )

            if status["version"]:
                _print_version_status(
                    assessment, status["version"], tool_path, tool_config
                )

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
                for copy in shadowed_copies(tool_name):
                    label = format_install_method(
                        copy.install["method"], copy.install["detail"]
                    )
                    warning(f"  Shadowed:     {copy.path} ({label})")
                    hint = removal_hint(copy)
                    if hint:
                        info(f"  To remove it: {hint}")

            if status["user"]:
                print(f"  User:         {status['user']}")

            if status["usage"]:
                print(f"  Usage:        {status['usage']}")

            if status["errors"]:
                for err_msg in status["errors"]:
                    warning(f"  {err_msg}")

        print()

    for message in linked_version_mismatches():
        warning(message)

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

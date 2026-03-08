"""Read-only CLI commands: list and status."""

import argparse
import platform
import shutil
from typing import List

from code_aide.constants import Colors, PACKAGE_MANAGERS, TOOLS
from code_aide.detection import (
    format_install_method,
    format_migration_warning,
    get_brew_package_info,
    get_system_package_info,
    detect_install_method,
)
from code_aide.console import command_exists, info, warning
from code_aide.prereqs import detect_package_manager, is_tool_installed
from code_aide.status import (
    get_tool_status,
    print_brew_version_status,
    print_system_version_status,
)
from code_aide.versions import (
    extract_version_from_string,
    status_version_matches_latest,
    version_is_newer,
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
        print(f"  Managed by:   {tool_config['install_type']} (code-aide)")

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
        "brew_formula": "brew",
        "brew_cask": "cask",
        "npm": "npm",
        "brew_npm": "brew-npm",
        "system": "system",
        "script": "script",
        "direct_download": "download",
    }
    return labels.get(method or "", method or "unknown")


def _compact_version_status(
    version: str | None, latest_version: str | None
) -> tuple[str, str]:
    """Return (version_str, status_indicator) for compact display."""
    if not version:
        return ("", "")
    ver = extract_version_from_string(version) or version
    if not latest_version:
        return (ver, "")
    if status_version_matches_latest(version, latest_version):
        return (ver, f"{Colors.GREEN}ok{Colors.NC}")
    if ver and version_is_newer(ver, latest_version):
        return (ver, f"{Colors.YELLOW}newer{Colors.NC}")
    return (ver, f"{Colors.YELLOW}old{Colors.NC}")


def cmd_status_compact() -> None:
    """Show compact one-line-per-tool status."""
    rows: list[tuple[str, str, str, str, str]] = []
    for tool_name, tool_config in TOOLS.items():
        name = tool_config["command"]
        status = get_tool_status(tool_name, tool_config)

        if not status["installed"]:
            opt_in = not tool_config.get("default_install", True)
            if opt_in:
                state = "opt-in"
            else:
                state = f"{Colors.RED}missing{Colors.NC}"
            rows.append((name, state, "", "", ""))
            continue

        tool_path = shutil.which(tool_config["command"]) or ""
        install_info = detect_install_method(tool_name)
        method = _short_install_method(install_info["method"])
        latest_version = tool_config.get("latest_version")
        ver, ver_status = _compact_version_status(status["version"], latest_version)

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
    migration_count = 0
    config_outdated: List[str] = []

    for tool_name, tool_config in TOOLS.items():
        print(f"{Colors.BLUE}{tool_config['name']}{Colors.NC}")

        status = get_tool_status(tool_name, tool_config)

        if not status["installed"]:
            print(f"  Status:       {Colors.RED}✗ Not installed{Colors.NC}")
        else:
            print(f"  Status:       {Colors.GREEN}✓ Installed{Colors.NC}")

            tool_path = shutil.which(tool_config["command"])
            install_info = detect_install_method(tool_name)
            is_system = install_info["method"] == "system"

            if status["version"]:
                latest_version = tool_config.get("latest_version")

                if is_system and tool_path:
                    pkg_info = get_system_package_info(tool_path)
                    print_system_version_status(
                        status["version"], latest_version, pkg_info
                    )
                elif install_info["method"] in ("brew_formula", "brew_cask"):
                    pkg_info = get_brew_package_info(
                        install_info["method"], install_info["detail"]
                    )
                    if pkg_info.get("available_version"):
                        print_brew_version_status(
                            status["version"], latest_version, pkg_info
                        )
                        if pkg_info.get("outdated"):
                            outdated_count += 1
                    elif latest_version:
                        if status_version_matches_latest(
                            status["version"], latest_version
                        ):
                            version_annotation = (
                                f"  Version:      {status['version']} "
                                f"{Colors.GREEN}(up to date){Colors.NC}"
                            )
                        else:
                            installed_ver = extract_version_from_string(
                                status["version"]
                            )
                            if installed_ver and version_is_newer(
                                installed_ver, latest_version
                            ):
                                version_annotation = (
                                    f"  Version:      {status['version']} "
                                    f"{Colors.YELLOW}(newer than configured "
                                    f"{latest_version}){Colors.NC}"
                                )
                                config_outdated.append(tool_name)
                            else:
                                version_annotation = (
                                    f"  Version:      {status['version']} "
                                    f"{Colors.YELLOW}(latest: {latest_version}){Colors.NC}"
                                )
                                outdated_count += 1
                        print(version_annotation)
                elif latest_version:
                    if status_version_matches_latest(status["version"], latest_version):
                        version_annotation = (
                            f"  Version:      {status['version']} "
                            f"{Colors.GREEN}(up to date){Colors.NC}"
                        )
                    else:
                        installed_ver = extract_version_from_string(status["version"])
                        if installed_ver and version_is_newer(
                            installed_ver, latest_version
                        ):
                            version_annotation = (
                                f"  Version:      {status['version']} "
                                f"{Colors.YELLOW}(newer than configured "
                                f"{latest_version}){Colors.NC}"
                            )
                            config_outdated.append(tool_name)
                        else:
                            version_annotation = (
                                f"  Version:      {status['version']} "
                                f"{Colors.YELLOW}(latest: {latest_version}){Colors.NC}"
                            )
                            outdated_count += 1
                    print(version_annotation)
                else:
                    print(f"  Version:      {status['version']}")

            if tool_path:
                print(f"  Location:     {tool_path}")
                print(
                    "  Installed via: "
                    f"{format_install_method(install_info['method'], install_info['detail'])}"
                )
                migration_msg = format_migration_warning(tool_name)
                if migration_msg:
                    warning(f"  {migration_msg}")
                    migration_count += 1

            if status["user"]:
                print(f"  User:         {status['user']}")

            if status["usage"]:
                print(f"  Usage:        {status['usage']}")

            if status["errors"]:
                for err_msg in status["errors"]:
                    warning(f"  {err_msg}")

        print()

    if config_outdated:
        tools_str = " ".join(config_outdated)
        print(
            f"{Colors.YELLOW}Configured version outdated for: "
            f"{', '.join(config_outdated)}. Run 'code-aide update-versions "
            f"{tools_str}' to update.{Colors.NC}"
        )
    if outdated_count > 0:
        print(
            f"{Colors.YELLOW}{outdated_count} tool(s) can be upgraded with "
            f"'code-aide upgrade'.{Colors.NC}"
        )
    if migration_count > 0:
        print(
            f"{Colors.YELLOW}{migration_count} tool(s) need migration to a "
            f"new install method. Run 'code-aide upgrade' to migrate.{Colors.NC}"
        )

"""Read-only CLI commands: list and status."""

import argparse
import platform
import shutil
from typing import List

from code_aide.constants import Colors, PACKAGE_MANAGERS, TOOLS
from code_aide.detection import (
    format_install_method,
    get_system_package_info,
    detect_install_method,
)
from code_aide.console import command_exists, info, warning
from code_aide.prereqs import detect_package_manager, is_tool_installed
from code_aide.status import print_system_version_status, get_tool_status
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


def cmd_status(args: argparse.Namespace) -> None:
    """Handle status command."""
    print("AI Coding CLI Tools Status:")
    print("=" * 70)
    print()

    outdated_count = 0
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

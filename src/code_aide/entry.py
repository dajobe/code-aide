"""Argument parser and CLI entrypoint."""

import argparse

from code_aide import __version__
from code_aide.commands_actions import (
    cmd_install,
    cmd_remove,
    cmd_update_versions,
    cmd_upgrade,
)
from code_aide.commands_tools import cmd_list, cmd_status
from code_aide.constants import TOOLS


def main() -> None:
    """Main function."""
    available_tools = ", ".join(TOOLS.keys())
    parser = argparse.ArgumentParser(
        description="Manage AI coding CLI tools",
        epilog=f"Available tools: {available_tools}",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    list_parser = subparsers.add_parser(
        "list", help="List available tools and their status"
    )
    list_parser.set_defaults(func=cmd_list)

    status_parser = subparsers.add_parser(
        "status", help="Show detailed status for installed tools"
    )
    status_parser.set_defaults(func=cmd_status)

    install_parser = subparsers.add_parser("install", help="Install tools")
    install_parser.add_argument(
        "tools",
        nargs="*",
        help="Tools to install (default: all)",
    )
    install_parser.add_argument(
        "-p",
        "--install-prerequisites",
        action="store_true",
        help="Automatically install prerequisites (Node.js, npm) "
        "using system package manager",
    )
    install_parser.add_argument(
        "-n",
        "--dryrun",
        action="store_true",
        help="Verify SHA256 checksums without installing (dry run mode)",
    )
    install_parser.set_defaults(func=cmd_install)

    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade tools")
    upgrade_parser.add_argument(
        "tools",
        nargs="*",
        help="Tools to upgrade (default: out-of-date only)",
    )
    upgrade_parser.set_defaults(func=cmd_upgrade)

    remove_parser = subparsers.add_parser("remove", help="Remove tools")
    remove_parser.add_argument(
        "tools",
        nargs="*",
        help="Tools to remove (default: all)",
    )
    remove_parser.set_defaults(func=cmd_remove)

    update_versions_parser = subparsers.add_parser(
        "update-versions",
        help="Check upstream sources for latest tool versions",
    )
    update_versions_parser.add_argument(
        "tools",
        nargs="*",
        help="Specific tools to check (default: all)",
    )
    update_versions_parser.add_argument(
        "-n",
        "--dryrun",
        action="store_true",
        help="Show changes only, do not write updates",
    )
    update_versions_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Auto-apply updates without prompting",
    )
    update_versions_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show full SHA256 hashes",
    )
    update_versions_parser.add_argument(
        "-b",
        "--bundled",
        action="store_true",
        help="Update bundled data/tools.json instead of user cache (developer use)",
    )
    update_versions_parser.set_defaults(func=cmd_update_versions)

    args = parser.parse_args()
    if not args.command:
        cmd_status(args)
    else:
        args.func(args)

"""Argument parser and CLI entrypoint."""

import argparse
import logging

from code_aide import __version__
from code_aide.commands_actions import (
    cmd_clean,
    cmd_install,
    cmd_remove,
    cmd_update_versions,
    cmd_upgrade,
)
from code_aide.commands_tools import cmd_list, cmd_status
from code_aide.constants import TOOLS


def _configure_logging(debug: bool) -> None:
    """Configure root logger.

    With ``--debug`` we emit DEBUG-level messages to stderr; otherwise the
    package logger stays at WARNING so ``_logger.debug`` calls in the codebase
    are silent in normal operation.
    """
    level = logging.DEBUG if debug else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(name)s: %(message)s",
        force=True,
    )


def main() -> None:
    """Main function."""
    available_tools = ", ".join(TOOLS.keys())
    parser = argparse.ArgumentParser(
        prog="code-aide",
        description="Manage AI coding CLI tools",
        epilog=f"Available tools: {available_tools}",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging to stderr",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    list_parser = subparsers.add_parser(
        "list", help="List available tools and their status"
    )
    list_parser.set_defaults(func=cmd_list)

    status_parser = subparsers.add_parser(
        "status", help="Show tool status (compact by default)"
    )
    status_parser.add_argument(
        "-l",
        "--long",
        action="store_true",
        help="Show detailed multi-line status",
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
    install_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Reinstall even if the command already exists in PATH",
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
    remove_parser.add_argument(
        "-n",
        "--dryrun",
        action="store_true",
        help="Show what would be removed without removing",
    )
    remove_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Do not prompt for confirmation",
    )
    clean_parser = subparsers.add_parser(
        "clean",
        help="Remove stale direct-download version directories",
    )
    clean_parser.add_argument(
        "tools",
        nargs="*",
        help="Tools to clean (default: direct-download tools)",
    )
    clean_parser.add_argument(
        "-n",
        "--dryrun",
        action="store_true",
        help="Show what would be removed without removing",
    )
    clean_parser.set_defaults(func=cmd_clean)

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
    update_versions_parser.set_defaults(func=cmd_update_versions)

    args = parser.parse_args()
    _configure_logging(getattr(args, "debug", False))
    if not args.command:
        cmd_status(args)
    else:
        args.func(args)

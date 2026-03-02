"""Unit tests for mutating CLI commands."""

import contextlib
import io
import sys
import unittest
from unittest import mock

from code_aide import commands_actions
from code_aide import entry


class TestCmdInstall(unittest.TestCase):
    """Tests for cmd_install."""

    def test_dryrun_uses_only_default_tools_and_skips_prereq_check(self):
        tools = {
            "default_tool": {
                "name": "Default Tool",
                "command": "default",
                "default_install": True,
                "next_steps": "run default",
            },
            "opt_in_tool": {
                "name": "Opt-in Tool",
                "command": "optin",
                "default_install": False,
                "next_steps": "run optin",
            },
        }
        args = type(
            "Args",
            (),
            {"tools": [], "dryrun": True, "install_prerequisites": False},
        )()

        with (
            mock.patch.dict(commands_actions.TOOLS, tools, clear=True),
            mock.patch.object(commands_actions, "validate_tools"),
            mock.patch.object(
                commands_actions, "install_tool", return_value=True
            ) as mock_install_tool,
            mock.patch.object(commands_actions, "check_prerequisites") as mock_prereqs,
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_actions.cmd_install(args)

        mock_install_tool.assert_called_once_with("default_tool", dryrun=True)
        mock_prereqs.assert_not_called()


class TestCmdUpdateVersions(unittest.TestCase):
    """Tests for cmd_update_versions."""

    def test_invalid_tool_exits(self):
        args = type(
            "Args",
            (),
            {
                "tools": ["missing"],
                "dryrun": False,
                "yes": False,
                "verbose": False,
            },
        )()
        with mock.patch.object(
            commands_actions,
            "load_bundled_tools",
            return_value={
                "tools": {"ok": {"install_type": "npm", "npm_package": "pkg"}}
            },
        ):
            with self.assertRaises(SystemExit):
                commands_actions.cmd_update_versions(args)

    def test_dry_run_with_no_changes_does_not_write_cache(self):
        args = type(
            "Args",
            (),
            {
                "tools": [],
                "dryrun": True,
                "yes": False,
                "verbose": False,
            },
        )()
        with (
            mock.patch.object(
                commands_actions,
                "load_bundled_tools",
                return_value={
                    "tools": {
                        "ok": {
                            "install_type": "npm",
                            "npm_package": "pkg",
                            "latest_version": "1.0.0",
                            "latest_date": "2026-01-01",
                        }
                    }
                },
            ),
            mock.patch.object(commands_actions, "load_versions_cache", return_value={}),
            mock.patch.object(
                commands_actions,
                "check_npm_tool",
                return_value={
                    "tool": "ok",
                    "type": "npm",
                    "version": "1.0.0",
                    "date": "2026-01-01",
                    "status": "ok",
                    "update": None,
                },
            ),
            mock.patch.object(commands_actions, "print_check_results_table"),
            mock.patch.object(commands_actions, "save_updated_versions") as mock_save,
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_actions.cmd_update_versions(args)
        self.assertIn("No upstream config changes detected.", buf.getvalue())
        mock_save.assert_not_called()


class TestUpgradeNoArgsParsing(unittest.TestCase):
    """Test that 'code-aide upgrade' with no arguments parses successfully."""

    def test_upgrade_with_no_args_parses_to_empty_tools_list(self):
        with (
            mock.patch.object(sys, "argv", ["code-aide", "upgrade"]),
            mock.patch.object(entry, "cmd_upgrade") as mock_upgrade,
        ):
            entry.main()
        mock_upgrade.assert_called_once()
        (args,) = mock_upgrade.call_args[0]
        self.assertEqual(args.command, "upgrade")
        self.assertEqual(args.tools, [])

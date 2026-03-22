"""Unit tests for mutating CLI commands."""

import contextlib
import io
import sys
import unittest
from unittest import mock

from code_aide import commands_actions
from code_aide import entry
from code_aide.operations import UpgradeResult


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


class TestCmdUpgrade(unittest.TestCase):
    """Tests for cmd_upgrade output handling."""

    def test_unchanged_upgrades_are_not_reported_as_updated(self):
        tools = {
            "test": {
                "name": "Test Tool",
                "command": "test",
                "latest_version": "2.0.0",
            }
        }
        args = type("Args", (), {"tools": ["test"]})()

        with (
            mock.patch.dict(commands_actions.TOOLS, tools, clear=True),
            mock.patch.object(commands_actions, "validate_tools"),
            mock.patch.object(commands_actions, "is_tool_installed", return_value=True),
            mock.patch.object(
                commands_actions,
                "upgrade_tool",
                return_value=UpgradeResult.UNCHANGED,
            ),
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_actions.cmd_upgrade(args)

        output = buf.getvalue()
        self.assertIn("No package-manager change: test", output)
        self.assertNotIn("Successfully updated: test", output)

    def test_default_upgrade_skips_brew_tool_when_homebrew_not_outdated(self):
        tools = {
            "brewtool": {
                "name": "Brew Tool",
                "command": "brewtool",
                "latest_version": "9.9.9",
            }
        }
        args = type("Args", (), {"tools": []})()

        with (
            mock.patch.dict(commands_actions.TOOLS, tools, clear=True),
            mock.patch.object(commands_actions, "validate_tools"),
            mock.patch.object(commands_actions, "is_tool_installed", return_value=True),
            mock.patch(
                "code_aide.status.detect_install_method",
                return_value={"method": "brew_formula", "detail": "brewtool"},
            ),
            mock.patch(
                "code_aide.status.get_brew_package_info",
                return_value={
                    "package": "brewtool",
                    "installed_version": "1.0.0",
                    "available_version": "1.0.0",
                    "available_date": None,
                    "outdated": False,
                },
            ),
            mock.patch.object(commands_actions, "upgrade_tool") as mock_upgrade,
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_actions.cmd_upgrade(args)

        output = buf.getvalue()
        self.assertIn("All installed tools are up to date", output)
        mock_upgrade.assert_not_called()

    def test_default_upgrade_skips_tool_when_installed_is_newer_than_catalog(self):
        tools = {
            "x": {
                "name": "Example Tool",
                "command": "example",
                "install_type": "script",
                "latest_version": "1.0.0",
            }
        }
        args = type("Args", (), {"tools": []})()

        with (
            mock.patch.dict(commands_actions.TOOLS, tools, clear=True),
            mock.patch.object(commands_actions, "validate_tools"),
            mock.patch.object(commands_actions, "is_tool_installed", return_value=True),
            mock.patch(
                "code_aide.status.detect_install_method",
                return_value={"method": "script", "detail": None},
            ),
            mock.patch(
                "code_aide.status.get_tool_status",
                return_value={"installed": True, "version": "2.0.0"},
            ),
            mock.patch.object(commands_actions, "upgrade_tool") as mock_upgrade,
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_actions.cmd_upgrade(args)

        output = buf.getvalue()
        self.assertIn("All installed tools are up to date", output)
        mock_upgrade.assert_not_called()

    def test_default_upgrade_skips_system_managed_tool(self):
        tools = {
            "sys": {
                "name": "System Tool",
                "command": "sys-tool",
                "install_type": "script",
                "latest_version": "2.0.0",
            }
        }
        args = type("Args", (), {"tools": []})()

        with (
            mock.patch.dict(commands_actions.TOOLS, tools, clear=True),
            mock.patch.object(commands_actions, "validate_tools"),
            mock.patch.object(commands_actions, "is_tool_installed", return_value=True),
            mock.patch(
                "code_aide.status.detect_install_method",
                return_value={"method": "system", "detail": "/usr/bin/sys-tool"},
            ),
            mock.patch(
                "code_aide.status.get_system_package_info",
                return_value={
                    "package": "dev-util/sys-tool",
                    "installed_version": "2.0.0",
                    "available_version": "2.0.0",
                },
            ),
            mock.patch(
                "code_aide.status.shutil.which", return_value="/usr/bin/sys-tool"
            ),
            mock.patch.object(commands_actions, "upgrade_tool") as mock_upgrade,
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_actions.cmd_upgrade(args)

        output = buf.getvalue()
        self.assertIn("All installed tools are up to date", output)
        mock_upgrade.assert_not_called()

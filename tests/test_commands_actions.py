"""Unit tests for mutating CLI commands."""

import contextlib
import io
import sys
import unittest
from unittest import mock

from code_aide import constants, commands_actions
from code_aide import entry
from code_aide.install import InstallOutcome
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
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(commands_actions, "validate_tools"),
            mock.patch.object(
                commands_actions, "install_tool", return_value=InstallOutcome(True)
            ) as mock_install_tool,
            mock.patch.object(commands_actions, "check_prerequisites") as mock_prereqs,
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_actions.cmd_install(args)

        mock_install_tool.assert_called_once_with("default_tool", dryrun=True)
        mock_prereqs.assert_not_called()

    def test_checks_bin_directories_reported_by_installers(self):
        tools = {
            "test": {
                "name": "Test Tool",
                "command": "test",
                "install_type": "npm",
                "next_steps": "run test",
            }
        }
        args = type(
            "Args",
            (),
            {"tools": ["test"], "dryrun": False, "install_prerequisites": False},
        )()

        with (
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(commands_actions, "validate_tools"),
            mock.patch.object(commands_actions, "check_prerequisites"),
            mock.patch.object(
                commands_actions,
                "install_tool",
                return_value=InstallOutcome(True, ("/home/test/.npm-packages/bin",)),
            ),
            mock.patch.object(
                commands_actions, "check_path_directories"
            ) as mock_check_path,
        ):
            commands_actions.cmd_install(args)

        mock_check_path.assert_called_once_with(["/home/test/.npm-packages/bin"])

    def test_resolves_tool_alias_before_installing(self):
        tools = {
            "antigravity": {
                "name": "Antigravity CLI",
                "command": "agy",
                "aliases": ["agy"],
                "install_type": "script",
                "next_steps": "run agy",
            }
        }
        args = type(
            "Args",
            (),
            {"tools": ["agy"], "dryrun": False, "install_prerequisites": False},
        )()

        with (
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(commands_actions, "check_prerequisites"),
            mock.patch.object(
                commands_actions,
                "install_tool",
                return_value=InstallOutcome(True),
            ) as mock_install,
            mock.patch.object(commands_actions, "check_path_directories"),
        ):
            commands_actions.cmd_install(args)

        mock_install.assert_called_once_with("antigravity", dryrun=False)


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

    def test_records_download_checksum_for_direct_download_tool(self):
        tools = {
            "dl": {
                "name": "DL Tool",
                "command": "dl",
                "install_type": "direct_download",
                "download_url_template": "https://example.com/{version}.tar.gz",
            }
        }
        args = type(
            "Args",
            (),
            {"tools": [], "dryrun": False, "yes": True, "verbose": False},
        )()

        with (
            mock.patch.object(
                commands_actions,
                "load_bundled_tools",
                return_value={"tools": tools},
            ),
            mock.patch.object(commands_actions, "load_versions_cache", return_value={}),
            mock.patch.object(
                commands_actions,
                "check_script_tool",
                return_value={
                    "tool": "dl",
                    "type": "direct_download",
                    "version": "1.0.0",
                    "date": "2026-08-01",
                    "status": "ok",
                    "update": None,
                },
            ),
            mock.patch.object(
                commands_actions,
                "fetch_download_checksum",
                return_value="c" * 64,
            ) as mock_checksum,
            mock.patch.object(commands_actions, "save_updated_versions") as mock_save,
            mock.patch("builtins.input") as mock_input,
            contextlib.redirect_stdout(io.StringIO()) as buf,
        ):
            commands_actions.cmd_update_versions(args)

        mock_checksum.assert_called_once()
        mock_input.assert_not_called()
        saved_tools = mock_save.call_args[0][0]
        self.assertEqual(saved_tools["dl"]["download_sha256"], "c" * 64)
        self.assertEqual(saved_tools["dl"]["latest_version"], "1.0.0")
        self.assertIn("Recorded download SHA256 for dl.", buf.getvalue())


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
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(commands_actions, "validate_tools"),
            mock.patch.object(commands_actions, "ensure_versions_cache"),
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
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(commands_actions, "validate_tools"),
            mock.patch.object(commands_actions, "ensure_versions_cache"),
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
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(commands_actions, "validate_tools"),
            mock.patch.object(commands_actions, "ensure_versions_cache"),
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
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(commands_actions, "validate_tools"),
            mock.patch.object(commands_actions, "ensure_versions_cache"),
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

    def test_default_upgrade_refreshes_versions_cache(self):
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
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(commands_actions, "validate_tools"),
            mock.patch.object(
                commands_actions, "ensure_versions_cache"
            ) as mock_refresh,
            mock.patch.object(commands_actions, "is_tool_installed", return_value=True),
            mock.patch(
                "code_aide.status.detect_install_method",
                return_value={"method": "script", "detail": None},
            ),
            mock.patch(
                "code_aide.status.get_tool_status",
                return_value={"installed": True, "version": "1.0.0"},
            ),
            mock.patch.object(commands_actions, "upgrade_tool") as mock_upgrade,
        ):
            commands_actions.cmd_upgrade(args)

        mock_refresh.assert_called_once()
        mock_upgrade.assert_not_called()

    def test_named_upgrade_does_not_refresh_versions_cache(self):
        tools = {
            "x": {
                "name": "Example Tool",
                "command": "example",
                "install_type": "script",
                "latest_version": "1.0.0",
            }
        }
        args = type("Args", (), {"tools": ["x"]})()

        with (
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(commands_actions, "validate_tools"),
            mock.patch.object(
                commands_actions, "ensure_versions_cache"
            ) as mock_refresh,
            mock.patch.object(commands_actions, "is_tool_installed", return_value=True),
            mock.patch.object(
                commands_actions,
                "upgrade_tool",
                return_value=UpgradeResult.UNCHANGED,
            ),
        ):
            commands_actions.cmd_upgrade(args)

        mock_refresh.assert_not_called()


class TestCmdRemove(unittest.TestCase):
    """Tests for cmd_remove confirmation and dry-run behavior."""

    @staticmethod
    def _args(**overrides):
        defaults = {"tools": [], "dryrun": False, "yes": False}
        defaults.update(overrides)
        return type("Args", (), defaults)()

    def test_remove_all_prompts_and_aborts_on_eof(self):
        args = self._args()
        with (
            mock.patch.dict(constants._TOOLS_DATA, {}, clear=True),
            mock.patch.object(commands_actions, "remove_tool") as mock_remove,
            mock.patch.object(
                commands_actions, "is_tool_installed", return_value=False
            ),
            mock.patch("builtins.input", side_effect=EOFError),
            contextlib.redirect_stdout(io.StringIO()) as buf,
        ):
            commands_actions.cmd_remove(args)

        self.assertIn("Aborted.", buf.getvalue())
        mock_remove.assert_not_called()

    def test_remove_all_declined_makes_no_changes(self):
        tools = {"a": {"name": "A", "command": "a"}}
        args = self._args()
        with (
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(commands_actions, "remove_tool") as mock_remove,
            mock.patch.object(commands_actions, "is_tool_installed", return_value=True),
            mock.patch("builtins.input", return_value="n"),
            contextlib.redirect_stdout(io.StringIO()) as buf,
        ):
            commands_actions.cmd_remove(args)

        mock_remove.assert_not_called()
        self.assertIn("Aborted.", buf.getvalue())

    def test_remove_all_confirmed_removes_all(self):
        tools = {
            "a": {"name": "A", "command": "a"},
            "b": {"name": "B", "command": "b"},
        }
        args = self._args()
        with (
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(
                commands_actions, "remove_tool", return_value=True
            ) as mock_remove,
            mock.patch.object(commands_actions, "is_tool_installed", return_value=True),
            mock.patch("builtins.input", return_value="y"),
            contextlib.redirect_stdout(io.StringIO()) as buf,
        ):
            commands_actions.cmd_remove(args)

        self.assertEqual(mock_remove.call_count, 2)
        self.assertIn("Successfully removed: a, b", buf.getvalue())

    def test_remove_all_with_yes_skips_prompt(self):
        tools = {"a": {"name": "A", "command": "a"}}
        args = self._args(yes=True)
        with (
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(
                commands_actions, "remove_tool", return_value=True
            ) as mock_remove,
            mock.patch.object(commands_actions, "is_tool_installed", return_value=True),
            mock.patch("builtins.input") as mock_input,
            contextlib.redirect_stdout(io.StringIO()) as buf,
        ):
            commands_actions.cmd_remove(args)

        mock_input.assert_not_called()
        mock_remove.assert_called_once_with("a")
        self.assertIn("Successfully removed: a", buf.getvalue())

    def test_dryrun_lists_without_removing(self):
        tools = {
            "a": {"name": "A", "command": "a"},
            "b": {"name": "B", "command": "b"},
        }
        args = self._args(dryrun=True)
        with (
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(commands_actions, "remove_tool") as mock_remove,
            mock.patch.object(
                commands_actions, "is_tool_installed", side_effect=[True, False]
            ),
            mock.patch("builtins.input") as mock_input,
            contextlib.redirect_stdout(io.StringIO()) as buf,
        ):
            commands_actions.cmd_remove(args)

        mock_remove.assert_not_called()
        mock_input.assert_not_called()
        output = buf.getvalue()
        self.assertIn("Would remove: a", output)
        self.assertIn("Not installed (skipped): b", output)
        self.assertIn("Dry run completed without removing anything!", output)

    def test_named_tools_skip_confirmation(self):
        tools = {"a": {"name": "A", "command": "a"}}
        args = self._args(tools=["a"])
        with (
            mock.patch.dict(constants._TOOLS_DATA, tools, clear=True),
            mock.patch.object(
                commands_actions, "remove_tool", return_value=True
            ) as mock_remove,
            mock.patch.object(commands_actions, "is_tool_installed", return_value=True),
            mock.patch("builtins.input") as mock_input,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            commands_actions.cmd_remove(args)

        mock_input.assert_not_called()
        mock_remove.assert_called_once_with("a")

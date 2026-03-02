"""Unit tests for mutate operations and action command selection."""

import os
import tempfile
import unittest
from unittest import mock

from code_aide import commands_actions as cli_commands_actions
from code_aide import operations as cli_operations


class TestRemoveToolDirectDownload(unittest.TestCase):
    """Tests for remove_tool with direct_download install method."""

    def test_removes_symlinks_and_all_version_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            versions_dir = os.path.join(td, "versions")
            os.makedirs(os.path.join(versions_dir, "1.0.0"))
            os.makedirs(os.path.join(versions_dir, "2.0.0"))

            bin_dir = os.path.join(td, "bin")
            os.makedirs(bin_dir)
            agent_link = os.path.join(bin_dir, "agent")
            legacy_link = os.path.join(bin_dir, "cursor-agent")
            os.symlink(
                os.path.join(versions_dir, "1.0.0", "cursor-agent"),
                agent_link,
            )
            os.symlink(
                os.path.join(versions_dir, "1.0.0", "cursor-agent"),
                legacy_link,
            )

            tool_name = "direct-download-test"
            tool_config = {
                "name": "Direct Download Test",
                "command": "agent",
                "install_type": "direct_download",
                "bin_dir": bin_dir,
                "symlinks": {
                    "agent": "cursor-agent",
                    "cursor-agent": "cursor-agent",
                },
                "install_dir": os.path.join(versions_dir, "{version}"),
            }

            with (
                mock.patch.dict(cli_operations.TOOLS, {tool_name: tool_config}),
                mock.patch.object(
                    cli_operations, "is_tool_installed", return_value=True
                ),
                mock.patch.object(
                    cli_operations,
                    "detect_install_method",
                    return_value={
                        "method": "direct_download",
                        "detail": None,
                    },
                ),
                mock.patch.object(
                    cli_operations.shutil, "which", return_value=agent_link
                ),
            ):
                result = cli_operations.remove_tool(tool_name)

            self.assertTrue(result)
            self.assertFalse(os.path.lexists(agent_link))
            self.assertFalse(os.path.lexists(legacy_link))
            self.assertFalse(os.path.exists(os.path.join(versions_dir, "1.0.0")))
            self.assertFalse(os.path.exists(os.path.join(versions_dir, "2.0.0")))


class TestRemoveToolScript(unittest.TestCase):
    """Tests for remove_tool with script install method."""

    def test_removes_binary(self):
        with tempfile.TemporaryDirectory() as td:
            binary_path = os.path.join(td, "amp")
            with open(binary_path, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\n")
            os.chmod(binary_path, 0o755)

            tool_name = "script-test"
            tool_config = {
                "name": "Script Test",
                "command": "amp",
                "install_type": "script",
                "install_url": "https://example.com/install.sh",
            }

            with (
                mock.patch.dict(cli_operations.TOOLS, {tool_name: tool_config}),
                mock.patch.object(
                    cli_operations, "is_tool_installed", return_value=True
                ),
                mock.patch.object(
                    cli_operations,
                    "detect_install_method",
                    return_value={
                        "method": "script",
                        "detail": None,
                    },
                ),
                mock.patch.object(
                    cli_operations.shutil, "which", return_value=binary_path
                ),
            ):
                result = cli_operations.remove_tool(tool_name)

            self.assertTrue(result)
            self.assertFalse(os.path.exists(binary_path))


class TestMigrateInstallMethod(unittest.TestCase):
    """Tests for migration in upgrade_tool."""

    def test_upgrade_triggers_migration_when_deprecated(self):
        """upgrade_tool calls _migrate_install_method for deprecated installs."""
        tool_config = {
            "name": "Test Tool",
            "command": "test-tool",
            "install_type": "script",
            "install_url": "https://example.com/install.sh",
        }
        with (
            mock.patch.dict(cli_operations.TOOLS, {"test": tool_config}),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=True),
            mock.patch.object(
                cli_operations, "is_deprecated_install", return_value=True
            ),
            mock.patch.object(
                cli_operations, "remove_tool", return_value=True
            ) as mock_remove,
            mock.patch.object(
                cli_operations, "install_tool", return_value=True
            ) as mock_install,
            mock.patch.object(
                cli_operations,
                "detect_install_method",
                return_value={"method": "npm", "detail": "test-pkg"},
            ),
        ):
            result = cli_operations.upgrade_tool("test")
        self.assertTrue(result)
        mock_remove.assert_called_once_with("test")
        mock_install.assert_called_once_with("test")

    def test_upgrade_normal_when_not_deprecated(self):
        """upgrade_tool does normal upgrade when not deprecated."""
        tool_config = {
            "name": "Test Tool",
            "command": "test-tool",
            "install_type": "script",
            "install_url": "https://example.com/install.sh",
            "install_sha256": "abc123",
        }
        with (
            mock.patch.dict(cli_operations.TOOLS, {"test": tool_config}),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=True),
            mock.patch.object(
                cli_operations, "is_deprecated_install", return_value=False
            ),
            mock.patch.object(
                cli_operations,
                "detect_install_method",
                return_value={"method": "script", "detail": "native installer"},
            ),
            mock.patch.object(
                cli_operations, "run_install_script", return_value=True
            ) as mock_script,
        ):
            result = cli_operations.upgrade_tool("test")
        self.assertTrue(result)
        mock_script.assert_called_once()

    def test_migration_fails_on_remove(self):
        """Migration fails if remove_tool returns False."""
        tool_config = {
            "name": "Test Tool",
            "command": "test-tool",
            "install_type": "script",
        }
        with (
            mock.patch.dict(cli_operations.TOOLS, {"test": tool_config}),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=True),
            mock.patch.object(
                cli_operations, "is_deprecated_install", return_value=True
            ),
            mock.patch.object(cli_operations, "remove_tool", return_value=False),
            mock.patch.object(
                cli_operations, "install_tool", return_value=True
            ) as mock_install,
            mock.patch.object(
                cli_operations,
                "detect_install_method",
                return_value={"method": "npm", "detail": "test-pkg"},
            ),
        ):
            result = cli_operations.upgrade_tool("test")
        self.assertFalse(result)
        mock_install.assert_not_called()

    def test_migration_fails_on_install(self):
        """Migration fails if install_tool returns False after remove."""
        tool_config = {
            "name": "Test Tool",
            "command": "test-tool",
            "install_type": "script",
        }
        with (
            mock.patch.dict(cli_operations.TOOLS, {"test": tool_config}),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=True),
            mock.patch.object(
                cli_operations, "is_deprecated_install", return_value=True
            ),
            mock.patch.object(cli_operations, "remove_tool", return_value=True),
            mock.patch.object(cli_operations, "install_tool", return_value=False),
            mock.patch.object(
                cli_operations,
                "detect_install_method",
                return_value={"method": "npm", "detail": "test-pkg"},
            ),
        ):
            result = cli_operations.upgrade_tool("test")
        self.assertFalse(result)


class TestCmdUpgradeDefaultSelection(unittest.TestCase):
    """Tests for default cmd_upgrade behavior."""

    def test_default_upgrades_only_out_of_date_installed_tools(self):
        tools = {
            "old": {
                "name": "Old Tool",
                "command": "old",
                "latest_version": "2.0.0",
            },
            "new": {
                "name": "New Tool",
                "command": "new",
                "latest_version": "1.0.0",
            },
            "missing": {
                "name": "Missing Tool",
                "command": "missing",
                "latest_version": "1.0.0",
            },
        }

        def _installed(name):
            return name in ("old", "new")

        def _status(name, _config):
            versions = {"old": "1.0.0", "new": "1.0.0"}
            return {"version": versions.get(name)}

        args = type("Args", (), {"tools": []})()

        with (
            mock.patch.dict(cli_commands_actions.TOOLS, tools, clear=True),
            mock.patch.object(
                cli_commands_actions, "is_tool_installed", side_effect=_installed
            ),
            mock.patch.object(
                cli_commands_actions, "is_deprecated_install", return_value=False
            ),
            mock.patch.object(
                cli_commands_actions, "get_tool_status", side_effect=_status
            ),
            mock.patch.object(
                cli_commands_actions, "upgrade_tool", return_value=True
            ) as mock_upgrade,
        ):
            cli_commands_actions.cmd_upgrade(args)

        mock_upgrade.assert_called_once_with("old")

    def test_default_upgrade_includes_deprecated_tools(self):
        """Tools with deprecated install methods are included even if version is current."""
        tools = {
            "current": {
                "name": "Current Tool",
                "command": "current",
                "latest_version": "1.0.0",
            },
        }

        args = type("Args", (), {"tools": []})()

        with (
            mock.patch.dict(cli_commands_actions.TOOLS, tools, clear=True),
            mock.patch.object(
                cli_commands_actions, "is_tool_installed", return_value=True
            ),
            mock.patch.object(
                cli_commands_actions, "is_deprecated_install", return_value=True
            ),
            mock.patch.object(
                cli_commands_actions,
                "get_tool_status",
                return_value={"version": "1.0.0"},
            ),
            mock.patch.object(
                cli_commands_actions, "upgrade_tool", return_value=True
            ) as mock_upgrade,
        ):
            cli_commands_actions.cmd_upgrade(args)

        mock_upgrade.assert_called_once_with("current")

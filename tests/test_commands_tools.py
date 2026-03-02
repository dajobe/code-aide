"""Unit tests for read-only CLI commands."""

import contextlib
import io
import unittest
from unittest import mock

from code_aide import commands_tools


class TestCmdList(unittest.TestCase):
    """Tests for cmd_list."""

    def test_lists_tools_without_runtime_probes(self):
        tools = {
            "x": {
                "name": "Example Tool",
                "command": "example",
                "install_type": "npm",
                "default_install": True,
            }
        }
        args = type("Args", (), {})()
        with (
            mock.patch.dict(commands_tools.TOOLS, tools, clear=True),
            mock.patch.object(commands_tools, "is_tool_installed", return_value=False),
            mock.patch.object(commands_tools, "command_exists", return_value=False),
            mock.patch.object(
                commands_tools, "detect_package_manager", return_value=None
            ),
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_tools.cmd_list(args)
        output = buf.getvalue()
        self.assertIn("Example Tool", output)
        self.assertIn("Managed by:   npm (code-aide)", output)
        self.assertIn("System Information:", output)


class TestCmdStatus(unittest.TestCase):
    """Tests for cmd_status."""

    def test_shows_upgradeable_count_for_outdated_tool(self):
        tools = {
            "x": {
                "name": "Example Tool",
                "command": "example",
                "install_type": "npm",
                "latest_version": "2.0.0",
            }
        }
        status = {
            "installed": True,
            "version": "1.0.0",
            "user": None,
            "usage": None,
            "errors": [],
        }
        args = type("Args", (), {})()
        with (
            mock.patch.dict(commands_tools.TOOLS, tools, clear=True),
            mock.patch.object(commands_tools, "get_tool_status", return_value=status),
            mock.patch.object(
                commands_tools.shutil, "which", return_value="/tmp/example"
            ),
            mock.patch.object(
                commands_tools,
                "detect_install_method",
                return_value={"method": "npm", "detail": "example-pkg"},
            ),
            mock.patch.object(
                commands_tools, "format_migration_warning", return_value=None
            ),
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_tools.cmd_status(args)
        output = buf.getvalue()
        self.assertIn("Example Tool", output)
        self.assertIn("tool(s) can be upgraded", output)

    def test_status_shows_migration_warning(self):
        """cmd_status shows migration warning for deprecated install."""
        tools = {
            "x": {
                "name": "Example Tool",
                "command": "example",
                "install_type": "script",
                "latest_version": "1.0.0",
            }
        }
        status = {
            "installed": True,
            "version": "1.0.0",
            "user": None,
            "usage": None,
            "errors": [],
        }
        args = type("Args", (), {})()
        with (
            mock.patch.dict(commands_tools.TOOLS, tools, clear=True),
            mock.patch.object(commands_tools, "get_tool_status", return_value=status),
            mock.patch.object(
                commands_tools.shutil, "which", return_value="/tmp/example"
            ),
            mock.patch.object(
                commands_tools,
                "detect_install_method",
                return_value={"method": "npm", "detail": "example-pkg"},
            ),
            mock.patch.object(
                commands_tools,
                "format_migration_warning",
                return_value="Installed via npm but configured method is script. "
                "Run 'code-aide upgrade x' to migrate.",
            ),
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_tools.cmd_status(args)
        output = buf.getvalue()
        self.assertIn("configured method is script", output)
        self.assertIn("tool(s) need migration", output)

    def test_list_shows_migration_warning(self):
        """cmd_list shows migration warning for deprecated install."""
        tools = {
            "x": {
                "name": "Example Tool",
                "command": "example",
                "install_type": "script",
                "default_install": True,
            }
        }
        args = type("Args", (), {})()
        with (
            mock.patch.dict(commands_tools.TOOLS, tools, clear=True),
            mock.patch.object(commands_tools, "is_tool_installed", return_value=True),
            mock.patch.object(
                commands_tools.shutil, "which", return_value="/tmp/example"
            ),
            mock.patch.object(
                commands_tools,
                "detect_install_method",
                return_value={"method": "npm", "detail": "example-pkg"},
            ),
            mock.patch.object(
                commands_tools,
                "format_migration_warning",
                return_value="Installed via npm but configured method is script. "
                "Run 'code-aide upgrade x' to migrate.",
            ),
            mock.patch.object(commands_tools, "command_exists", return_value=False),
            mock.patch.object(
                commands_tools, "detect_package_manager", return_value=None
            ),
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_tools.cmd_list(args)
        output = buf.getvalue()
        self.assertIn("configured method is script", output)

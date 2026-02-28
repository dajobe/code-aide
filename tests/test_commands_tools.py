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
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_tools.cmd_status(args)
        output = buf.getvalue()
        self.assertIn("Example Tool", output)
        self.assertIn("tool(s) can be upgraded", output)

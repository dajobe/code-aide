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
                commands_tools, "_detect_package_manager", return_value=None
            ),
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_tools.cmd_list(args)
        output = buf.getvalue()
        self.assertIn("Example Tool", output)
        self.assertIn("Managed by:   npm (code-aide)", output)
        self.assertIn("System Information:", output)


@mock.patch.object(commands_tools, "ensure_versions_cache")
class TestCmdStatus(unittest.TestCase):
    """Tests for cmd_status."""

    def test_shows_upgradeable_count_for_outdated_tool(self, _mock_cache):
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
        args = type("Args", (), {"long": True})()
        with (
            mock.patch.dict(commands_tools.TOOLS, tools, clear=True),
            mock.patch.object(
                commands_tools.shutil, "which", return_value="/tmp/example"
            ),
            mock.patch("code_aide.status.get_tool_status", return_value=status),
            mock.patch.object(
                commands_tools,
                "format_migration_warning",
                return_value=None,
            ),
            mock.patch.object(
                commands_tools,
                "detect_install_method",
                return_value={"method": "npm", "detail": "example-pkg"},
            ),
            mock.patch(
                "code_aide.status.detect_install_method",
                return_value={"method": "npm", "detail": "example-pkg"},
            ),
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_tools.cmd_status(args)
        output = buf.getvalue()
        self.assertIn("Example Tool", output)
        self.assertIn("tool(s) can be upgraded", output)
        self.assertIn(": x.", output)

    def test_brew_current_upstream_lag_does_not_count_as_upgradeable(self, _mock_cache):
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
        args = type("Args", (), {"long": True})()
        with (
            mock.patch.dict(commands_tools.TOOLS, tools, clear=True),
            mock.patch.object(
                commands_tools.shutil, "which", return_value="/opt/homebrew/bin/example"
            ),
            mock.patch("code_aide.status.get_tool_status", return_value=status),
            mock.patch.object(
                commands_tools,
                "format_migration_warning",
                return_value=None,
            ),
            mock.patch.object(
                commands_tools,
                "detect_install_method",
                return_value={"method": "brew_formula", "detail": "example"},
            ),
            mock.patch(
                "code_aide.status.detect_install_method",
                return_value={"method": "brew_formula", "detail": "example"},
            ),
            mock.patch(
                "code_aide.status.get_brew_package_info",
                return_value={
                    "package": "example",
                    "installed_version": "1.0.0",
                    "available_version": "1.0.0",
                    "available_date": None,
                    "outdated": False,
                },
            ),
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_tools.cmd_status(args)
        output = buf.getvalue()
        self.assertIn("Packaged:     1.0.0 (example)", output)
        self.assertIn("upstream: 2.0.0", output)
        self.assertNotIn("tool(s) can be upgraded", output)

    def test_installed_newer_than_catalog_shows_up_to_date(self, _mock_cache):
        """When the binary is newer than latest_version, do not nag update-versions."""
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
            "version": "2.0.0",
            "user": None,
            "usage": None,
            "errors": [],
        }
        args = type("Args", (), {"long": True})()
        with (
            mock.patch.dict(commands_tools.TOOLS, tools, clear=True),
            mock.patch.object(
                commands_tools.shutil, "which", return_value="/tmp/example"
            ),
            mock.patch("code_aide.status.get_tool_status", return_value=status),
            mock.patch.object(
                commands_tools,
                "format_migration_warning",
                return_value=None,
            ),
            mock.patch.object(
                commands_tools,
                "detect_install_method",
                return_value={"method": "script", "detail": None},
            ),
            mock.patch(
                "code_aide.status.detect_install_method",
                return_value={"method": "script", "detail": None},
            ),
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_tools.cmd_status(args)
        output = buf.getvalue()
        self.assertIn("(up to date)", output)
        self.assertNotIn("Configured version outdated", output)
        self.assertNotIn("update-versions", output)

    def test_status_shows_migration_warning(self, _mock_cache):
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
        args = type("Args", (), {"long": True})()
        with (
            mock.patch.dict(commands_tools.TOOLS, tools, clear=True),
            mock.patch.object(
                commands_tools.shutil, "which", return_value="/tmp/example"
            ),
            mock.patch("code_aide.status.get_tool_status", return_value=status),
            mock.patch.object(
                commands_tools,
                "detect_install_method",
                return_value={"method": "npm", "detail": "example-pkg"},
            ),
            mock.patch(
                "code_aide.status.detect_install_method",
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

    def test_compact_status_shows_ok_for_brew_tool_with_catalog_lag(self, _mock_cache):
        tools = {
            "x": {
                "name": "Example Tool",
                "command": "example",
                "install_type": "script",
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
            mock.patch.object(
                commands_tools.shutil, "which", return_value="/opt/homebrew/bin/example"
            ),
            mock.patch("code_aide.status.get_tool_status", return_value=status),
            mock.patch(
                "code_aide.status.detect_install_method",
                return_value={"method": "brew_formula", "detail": "example"},
            ),
            mock.patch(
                "code_aide.status.get_brew_package_info",
                return_value={
                    "package": "example",
                    "installed_version": "1.0.0",
                    "available_version": "1.0.0",
                    "available_date": None,
                    "outdated": False,
                },
            ),
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_tools.cmd_status(args)
        output = buf.getvalue()
        self.assertIn("example", output)
        self.assertIn("ok", output)
        self.assertNotIn("old", output)

    def test_list_shows_migration_warning(self, _mock_cache):
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
                commands_tools, "_detect_package_manager", return_value=None
            ),
        ):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                commands_tools.cmd_list(args)
        output = buf.getvalue()
        self.assertIn("configured method is script", output)

"""Unit tests for install-method detection and label formatting."""

import unittest
from unittest import mock

from code_aide import detection as cli_detection


class TestFormatInstallMethod(unittest.TestCase):
    """Tests for format_install_method."""

    def test_brew_npm_label(self):
        self.assertEqual(
            cli_detection.format_install_method("brew_npm", "@google/gemini-cli"),
            "Homebrew prefix npm-global (@google/gemini-cli)",
        )

    def test_brew_formula_label(self):
        self.assertEqual(
            cli_detection.format_install_method("brew_formula", "gemini-cli"),
            "Homebrew formula (gemini-cli)",
        )


class TestDetectInstallMethod(unittest.TestCase):
    """Tests for detect_install_method."""

    def test_unknown_tool(self):
        self.assertEqual(
            cli_detection.detect_install_method("does-not-exist"),
            {"method": None, "detail": None},
        )

    @mock.patch.object(cli_detection.os.path, "realpath")
    @mock.patch.object(cli_detection.shutil, "which")
    def test_detects_native_installer(self, mock_which, mock_realpath):
        mock_which.return_value = "/Users/test/.local/bin/claude"
        mock_realpath.return_value = (
            "/Users/test/.local/share/claude/versions/2.1.63/claude"
        )

        self.assertEqual(
            cli_detection.detect_install_method("claude"),
            {"method": "script", "detail": "native installer"},
        )

    @mock.patch.object(cli_detection.os.path, "realpath")
    @mock.patch.object(cli_detection.shutil, "which")
    def test_detects_npm_global_gemini(self, mock_which, mock_realpath):
        mock_which.return_value = "/Users/test/.local/bin/gemini"
        mock_realpath.return_value = (
            "/Users/test/.local/lib/node_modules/@google/gemini-cli/cli.js"
        )

        self.assertEqual(
            cli_detection.detect_install_method("gemini"),
            {"method": "npm", "detail": "@google/gemini-cli"},
        )

    @mock.patch.object(cli_detection.os.path, "realpath")
    @mock.patch.object(cli_detection.shutil, "which")
    def test_detects_system_package_opt(self, mock_which, mock_realpath):
        mock_which.return_value = "/opt/bin/claude"
        mock_realpath.return_value = "/opt/bin/claude"

        self.assertEqual(
            cli_detection.detect_install_method("claude"),
            {"method": "system", "detail": "/opt/bin/claude"},
        )

    @mock.patch.object(cli_detection.os.path, "realpath")
    @mock.patch.object(cli_detection.shutil, "which")
    def test_detects_system_package_usr_bin(self, mock_which, mock_realpath):
        mock_which.return_value = "/usr/bin/claude"
        mock_realpath.return_value = "/usr/bin/claude"

        self.assertEqual(
            cli_detection.detect_install_method("claude"),
            {"method": "system", "detail": "/usr/bin/claude"},
        )


class TestFormatInstallMethodSystem(unittest.TestCase):
    """Tests for format_install_method with system method."""

    def test_system_with_detail(self):
        self.assertEqual(
            cli_detection.format_install_method("system", "/opt/bin/claude"),
            "system package (/opt/bin/claude)",
        )

    def test_system_without_detail(self):
        self.assertEqual(
            cli_detection.format_install_method("system", None),
            "system package",
        )


class TestFormatInstallMethodDirectDownload(unittest.TestCase):
    """Tests for format_install_method with direct_download method."""

    def test_direct_download_label(self):
        self.assertEqual(
            cli_detection.format_install_method("direct_download", None),
            "direct download",
        )


class TestFormatInstallMethodScript(unittest.TestCase):
    """Tests for format_install_method with script method."""

    def test_script_label(self):
        self.assertEqual(
            cli_detection.format_install_method("script", None),
            "script",
        )


class TestIsDeprecatedInstall(unittest.TestCase):
    """Tests for is_deprecated_install."""

    def test_npm_to_script_is_deprecated(self):
        """npm detected but configured as script -> deprecated."""
        tool_config = {
            "name": "Test Tool",
            "command": "test-tool",
            "install_type": "script",
        }
        with (
            mock.patch.dict(cli_detection.TOOLS, {"test": tool_config}, clear=True),
            mock.patch.object(
                cli_detection,
                "detect_install_method",
                return_value={"method": "npm", "detail": "test-pkg"},
            ),
        ):
            self.assertTrue(cli_detection.is_deprecated_install("test"))

    def test_npm_to_direct_download_is_deprecated(self):
        """npm detected but configured as direct_download -> deprecated."""
        tool_config = {
            "name": "Test Tool",
            "command": "test-tool",
            "install_type": "direct_download",
        }
        with (
            mock.patch.dict(cli_detection.TOOLS, {"test": tool_config}, clear=True),
            mock.patch.object(
                cli_detection,
                "detect_install_method",
                return_value={"method": "npm", "detail": "test-pkg"},
            ),
        ):
            self.assertTrue(cli_detection.is_deprecated_install("test"))

    def test_brew_npm_to_script_is_deprecated(self):
        """brew_npm detected but configured as script -> deprecated."""
        tool_config = {
            "name": "Test Tool",
            "command": "test-tool",
            "install_type": "script",
        }
        with (
            mock.patch.dict(cli_detection.TOOLS, {"test": tool_config}, clear=True),
            mock.patch.object(
                cli_detection,
                "detect_install_method",
                return_value={"method": "brew_npm", "detail": "test-pkg"},
            ),
        ):
            self.assertTrue(cli_detection.is_deprecated_install("test"))

    def test_npm_to_npm_not_deprecated(self):
        """npm detected and configured as npm -> not deprecated."""
        tool_config = {
            "name": "Test Tool",
            "command": "test-tool",
            "install_type": "npm",
        }
        with (
            mock.patch.dict(cli_detection.TOOLS, {"test": tool_config}, clear=True),
            mock.patch.object(
                cli_detection,
                "detect_install_method",
                return_value={"method": "npm", "detail": "test-pkg"},
            ),
        ):
            self.assertFalse(cli_detection.is_deprecated_install("test"))

    def test_brew_formula_never_deprecated(self):
        """brew_formula is user-managed, never deprecated."""
        tool_config = {
            "name": "Test Tool",
            "command": "test-tool",
            "install_type": "script",
        }
        with (
            mock.patch.dict(cli_detection.TOOLS, {"test": tool_config}, clear=True),
            mock.patch.object(
                cli_detection,
                "detect_install_method",
                return_value={"method": "brew_formula", "detail": "test"},
            ),
        ):
            self.assertFalse(cli_detection.is_deprecated_install("test"))

    def test_system_never_deprecated(self):
        """system is user-managed, never deprecated."""
        tool_config = {
            "name": "Test Tool",
            "command": "test-tool",
            "install_type": "script",
        }
        with (
            mock.patch.dict(cli_detection.TOOLS, {"test": tool_config}, clear=True),
            mock.patch.object(
                cli_detection,
                "detect_install_method",
                return_value={"method": "system", "detail": "/usr/bin/test-tool"},
            ),
        ):
            self.assertFalse(cli_detection.is_deprecated_install("test"))

    def test_not_installed_not_deprecated(self):
        """Tool not installed (method=None) -> not deprecated."""
        tool_config = {
            "name": "Test Tool",
            "command": "test-tool",
            "install_type": "script",
        }
        with (
            mock.patch.dict(cli_detection.TOOLS, {"test": tool_config}, clear=True),
            mock.patch.object(
                cli_detection,
                "detect_install_method",
                return_value={"method": None, "detail": None},
            ),
        ):
            self.assertFalse(cli_detection.is_deprecated_install("test"))

    def test_unknown_tool_not_deprecated(self):
        """Unknown tool name -> not deprecated."""
        with mock.patch.dict(cli_detection.TOOLS, {}, clear=True):
            self.assertFalse(cli_detection.is_deprecated_install("no-such-tool"))


class TestFormatMigrationWarning(unittest.TestCase):
    """Tests for format_migration_warning."""

    def test_returns_warning_for_deprecated(self):
        """Returns a warning string when install is deprecated."""
        tool_config = {
            "name": "Test Tool",
            "command": "test-tool",
            "install_type": "script",
        }
        with (
            mock.patch.dict(cli_detection.TOOLS, {"test": tool_config}, clear=True),
            mock.patch.object(
                cli_detection,
                "detect_install_method",
                return_value={"method": "npm", "detail": "test-pkg"},
            ),
        ):
            msg = cli_detection.format_migration_warning("test")
            self.assertIsNotNone(msg)
            self.assertIn("npm", msg)
            self.assertIn("script", msg)
            self.assertIn("code-aide upgrade test", msg)

    def test_returns_none_when_not_deprecated(self):
        """Returns None when install is not deprecated."""
        tool_config = {
            "name": "Test Tool",
            "command": "test-tool",
            "install_type": "npm",
        }
        with (
            mock.patch.dict(cli_detection.TOOLS, {"test": tool_config}, clear=True),
            mock.patch.object(
                cli_detection,
                "detect_install_method",
                return_value={"method": "npm", "detail": "test-pkg"},
            ),
        ):
            self.assertIsNone(cli_detection.format_migration_warning("test"))

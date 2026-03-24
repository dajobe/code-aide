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
    def test_detects_npm_under_homebrew_prefix_as_npm(self, mock_which, mock_realpath):
        mock_which.return_value = "/opt/homebrew/bin/copilot"
        mock_realpath.return_value = (
            "/opt/homebrew/lib/node_modules/@github/copilot/bin/copilot.js"
        )

        self.assertEqual(
            cli_detection.detect_install_method("copilot"),
            {"method": "npm", "detail": "@github/copilot"},
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

    @mock.patch.object(cli_detection, "is_freebsd", return_value=True)
    @mock.patch.object(cli_detection, "_pkg_owns_file", return_value=True)
    @mock.patch.object(cli_detection.os.path, "realpath")
    @mock.patch.object(cli_detection.shutil, "which")
    def test_detects_freebsd_pkg(self, mock_which, mock_realpath, mock_pkg, mock_fbsd):
        mock_which.return_value = "/usr/local/bin/claude"
        mock_realpath.return_value = "/usr/local/bin/claude"

        self.assertEqual(
            cli_detection.detect_install_method("claude"),
            {"method": "pkg", "detail": "claude-code"},
        )

    @mock.patch.object(cli_detection, "is_freebsd", return_value=True)
    @mock.patch.object(cli_detection, "_pkg_owns_file", return_value=False)
    @mock.patch.object(cli_detection.os.path, "realpath")
    @mock.patch.object(cli_detection.shutil, "which")
    def test_freebsd_not_pkg_owned_falls_back_to_system(
        self, mock_which, mock_realpath, mock_pkg, mock_fbsd
    ):
        mock_which.return_value = "/usr/local/bin/claude"
        mock_realpath.return_value = "/usr/local/bin/claude"

        self.assertEqual(
            cli_detection.detect_install_method("claude"),
            {"method": "system", "detail": "/usr/local/bin/claude"},
        )

    @mock.patch.object(cli_detection, "is_freebsd", return_value=False)
    @mock.patch.object(cli_detection.os.path, "realpath")
    @mock.patch.object(cli_detection.shutil, "which")
    def test_not_freebsd_ignores_port(self, mock_which, mock_realpath, mock_fbsd):
        mock_which.return_value = "/usr/local/bin/claude"
        mock_realpath.return_value = "/usr/local/bin/claude"

        self.assertEqual(
            cli_detection.detect_install_method("claude"),
            {"method": "system", "detail": "/usr/local/bin/claude"},
        )


class TestFormatInstallMethodPkg(unittest.TestCase):
    """Tests for format_install_method with pkg method."""

    def test_pkg_with_detail(self):
        self.assertEqual(
            cli_detection.format_install_method("pkg", "claude-code"),
            "FreeBSD pkg (claude-code)",
        )

    def test_pkg_without_detail(self):
        self.assertEqual(
            cli_detection.format_install_method("pkg", None),
            "FreeBSD pkg",
        )


class TestPkgNeverDeprecated(unittest.TestCase):
    """Tests that pkg install method is never deprecated."""

    def test_pkg_never_deprecated(self):
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
                return_value={"method": "pkg", "detail": "test-tool"},
            ),
        ):
            self.assertFalse(cli_detection.is_deprecated_install("test"))


class TestGetPkgPackageInfo(unittest.TestCase):
    """Tests for get_pkg_package_info."""

    @mock.patch.object(cli_detection, "command_exists", return_value=False)
    def test_no_pkg_command(self, mock_cmd):
        result = cli_detection.get_pkg_package_info("claude-code")
        self.assertEqual(result["package"], "claude-code")
        self.assertIsNone(result["installed_version"])
        self.assertIsNone(result["available_version"])

    @mock.patch.object(cli_detection, "command_exists", return_value=True)
    @mock.patch.object(cli_detection.subprocess, "run")
    def test_parses_pkg_output(self, mock_run, mock_cmd):
        def side_effect(cmd, **kwargs):
            result = mock.Mock()
            if cmd[1] == "query":
                result.returncode = 0
                result.stdout = "2.1.62\n"
            elif cmd[1] == "rquery":
                result.returncode = 0
                result.stdout = "2.1.63\n"
            else:
                result.returncode = 1
                result.stdout = ""
            return result

        mock_run.side_effect = side_effect

        result = cli_detection.get_pkg_package_info("claude-code")
        self.assertEqual(result["installed_version"], "2.1.62")
        self.assertEqual(result["available_version"], "2.1.63")
        self.assertTrue(result["outdated"])

    @mock.patch.object(cli_detection, "command_exists", return_value=True)
    @mock.patch.object(cli_detection.subprocess, "run")
    def test_up_to_date(self, mock_run, mock_cmd):
        def side_effect(cmd, **kwargs):
            result = mock.Mock()
            result.returncode = 0
            result.stdout = "2.1.63\n"
            return result

        mock_run.side_effect = side_effect

        result = cli_detection.get_pkg_package_info("claude-code")
        self.assertEqual(result["installed_version"], "2.1.63")
        self.assertEqual(result["available_version"], "2.1.63")
        self.assertFalse(result["outdated"])

    @mock.patch.object(cli_detection, "command_exists", return_value=True)
    @mock.patch.object(cli_detection.subprocess, "run")
    def test_repo_passes_r_flag_to_rquery(self, mock_run, mock_cmd):
        calls = []

        def side_effect(cmd, **kwargs):
            calls.append(list(cmd))
            result = mock.Mock()
            result.returncode = 0
            result.stdout = "2.1.63\n"
            return result

        mock_run.side_effect = side_effect

        cli_detection.get_pkg_package_info("claude-code", repo="FreeBSD-latest")

        # pkg query (local) should NOT have -r
        self.assertEqual(calls[0], ["pkg", "query", "%v", "claude-code"])
        # pkg rquery (remote) should have -r
        self.assertEqual(
            calls[1],
            ["pkg", "rquery", "-r", "FreeBSD-latest", "%v", "claude-code"],
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

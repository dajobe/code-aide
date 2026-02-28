"""Unit tests for install-method detection and label formatting."""

import unittest
from unittest import mock

from code_aide import detection as cli_detection


class TestFormatInstallMethod(unittest.TestCase):
    """Tests for format_install_method."""

    def test_brew_npm_label(self):
        self.assertEqual(
            cli_detection.format_install_method(
                "brew_npm", "@anthropic-ai/claude-code"
            ),
            "Homebrew prefix npm-global (@anthropic-ai/claude-code)",
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
    def test_detects_brew_npm_wrapper(self, mock_which, mock_realpath):
        mock_which.return_value = "/opt/homebrew/bin/claude"
        mock_realpath.return_value = (
            "/opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/cli.js"
        )

        self.assertEqual(
            cli_detection.detect_install_method("claude"),
            {"method": "brew_npm", "detail": "@anthropic-ai/claude-code"},
        )

    @mock.patch.object(cli_detection.os.path, "realpath")
    @mock.patch.object(cli_detection.shutil, "which")
    def test_detects_plain_npm_global(self, mock_which, mock_realpath):
        mock_which.return_value = "/Users/test/.local/bin/claude"
        mock_realpath.return_value = (
            "/Users/test/.local/lib/node_modules/" "@anthropic-ai/claude-code/cli.js"
        )

        self.assertEqual(
            cli_detection.detect_install_method("claude"),
            {"method": "npm", "detail": "@anthropic-ai/claude-code"},
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


class TestFormatInstallMethodSelfManaged(unittest.TestCase):
    """Tests for format_install_method with self_managed method."""

    def test_self_managed_label(self):
        self.assertEqual(
            cli_detection.format_install_method("self_managed", None),
            "self-managed",
        )

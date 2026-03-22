"""Unit tests for typed install type and method helpers."""

import unittest
from unittest import mock

from code_aide import detection as cli_detection
from code_aide.install_types import (
    InstallMethod,
    InstallType,
    get_tool_install_type,
    install_method_from_type,
    parse_install_method,
    parse_install_type,
)


class TestInstallTypeParsing(unittest.TestCase):
    """Tests for install type parsing helpers."""

    def test_parse_install_type_returns_enum(self):
        self.assertEqual(parse_install_type("script"), InstallType.SCRIPT)

    def test_parse_unknown_install_type_returns_none(self):
        self.assertIsNone(parse_install_type("unknown"))

    def test_get_tool_install_type_returns_enum(self):
        self.assertEqual(
            get_tool_install_type({"install_type": "direct_download"}),
            InstallType.DIRECT_DOWNLOAD,
        )


class TestInstallMethodParsing(unittest.TestCase):
    """Tests for install method parsing helpers."""

    def test_parse_install_method_returns_enum(self):
        self.assertEqual(
            parse_install_method("brew_formula"), InstallMethod.BREW_FORMULA
        )

    def test_parse_install_method_maps_install_type_values(self):
        self.assertEqual(parse_install_method("script"), InstallMethod.SCRIPT)

    def test_install_method_from_type_returns_matching_method(self):
        self.assertEqual(install_method_from_type(InstallType.NPM), InstallMethod.NPM)


class TestDetectionTypedMethods(unittest.TestCase):
    """Tests for enum-returning detect_install_method behavior."""

    @mock.patch.object(cli_detection.os.path, "realpath")
    @mock.patch.object(cli_detection.shutil, "which")
    def test_detect_install_method_returns_install_method_enum(
        self, mock_which, mock_realpath
    ):
        mock_which.return_value = "/usr/bin/claude"
        mock_realpath.return_value = "/usr/bin/claude"

        result = cli_detection.detect_install_method("claude")
        self.assertEqual(result["method"], InstallMethod.SYSTEM)
        self.assertIsInstance(result["method"], InstallMethod)

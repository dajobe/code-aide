"""Unit tests for package version info lookups."""

import subprocess
import unittest
from unittest import mock

from code_aide import package_info as cli_package_info


class TestGetSystemPackageInfo(unittest.TestCase):
    """Tests for get_system_package_info."""

    def test_returns_empty_info_when_qfile_missing(self):
        with mock.patch.object(cli_package_info, "command_exists", return_value=False):
            info = cli_package_info.get_system_package_info("/usr/bin/tool")
        self.assertEqual(
            info,
            {
                "package": None,
                "installed_version": None,
                "available_version": None,
                "available_date": None,
            },
        )

    def test_returns_empty_info_when_qfile_finds_nothing(self):
        no_match = subprocess.CompletedProcess(["qfile"], 1, stdout="", stderr="")
        with (
            mock.patch.object(cli_package_info, "command_exists", return_value=True),
            mock.patch.object(
                cli_package_info.subprocess, "run", return_value=no_match
            ),
        ):
            info = cli_package_info.get_system_package_info("/usr/bin/tool")
        self.assertIsNone(info["package"])
        self.assertIsNone(info["installed_version"])

    def test_resolves_installed_version_through_qlist_and_qatom(self):
        responses = [
            subprocess.CompletedProcess(
                ["qfile"], 0, stdout="dev-util/tool\n", stderr=""
            ),
            subprocess.CompletedProcess(
                ["qlist"], 0, stdout="dev-util/tool-1.4.2\n", stderr=""
            ),
            subprocess.CompletedProcess(["qatom"], 0, stdout="1.4.2\n", stderr=""),
        ]
        with (
            mock.patch.object(cli_package_info, "command_exists", return_value=True),
            mock.patch.object(
                cli_package_info.subprocess, "run", side_effect=responses
            ),
            mock.patch.object(cli_package_info.globmod, "glob", return_value=[]),
        ):
            info = cli_package_info.get_system_package_info("/usr/bin/tool")
        self.assertEqual(info["package"], "dev-util/tool")
        self.assertEqual(info["installed_version"], "1.4.2")

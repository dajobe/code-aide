"""Tests for finding shadowed copies of a command on PATH."""

import os
import tempfile
import unittest
from unittest import mock

from code_aide import operation_handlers as cli_handlers
from code_aide import operations as cli_operations
from code_aide import path_copies
from code_aide.detection_types import DetectedInstallInfo

TOOL = {"name": "Test Tool", "command": "tt", "install_type": "npm"}


def _npm_install(prefix: str, package: str = "tt-pkg") -> str:
    """Create a fake npm global install of `tt` under prefix; return bin dir."""
    module_bin = os.path.join(prefix, "lib", "node_modules", package, "bin")
    os.makedirs(module_bin)
    script = os.path.join(module_bin, "tt.mjs")
    with open(script, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\n")
    os.chmod(script, 0o755)
    bin_dir = os.path.join(prefix, "bin")
    os.makedirs(bin_dir)
    os.symlink(script, os.path.join(bin_dir, "tt"))
    return bin_dir


class TestFindCommandCopies(unittest.TestCase):
    """Tests for find_command_copies and removal hints."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self._tmp.name)
        patcher = mock.patch.object(path_copies, "TOOLS", {"tt": TOOL})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def _with_path(self, *dirs):
        return mock.patch.dict(os.environ, {"PATH": os.pathsep.join(dirs)})

    def test_two_npm_prefixes_are_reported_in_path_order(self):
        first = _npm_install(os.path.join(self.root, "user"))
        second = _npm_install(os.path.join(self.root, "brew"))
        with self._with_path(first, second, first):
            copies = path_copies.find_command_copies("tt")
            shadowed = path_copies.shadowed_copies("tt")

        self.assertEqual(
            [c.path for c in copies],
            [os.path.join(first, "tt"), os.path.join(second, "tt")],
        )
        self.assertEqual(len(shadowed), 1)
        self.assertEqual(shadowed[0].install, {"method": "npm", "detail": "tt-pkg"})
        self.assertEqual(
            path_copies.removal_hint(shadowed[0]),
            f"npm uninstall -g --prefix {os.path.join(self.root, 'brew')} tt-pkg",
        )

    def test_symlinks_to_one_file_count_once(self):
        bin_dir = _npm_install(os.path.join(self.root, "user"))
        other = os.path.join(self.root, "other")
        os.makedirs(other)
        os.symlink(os.path.join(bin_dir, "tt"), os.path.join(other, "tt"))
        with self._with_path(bin_dir, other):
            self.assertEqual(path_copies.shadowed_copies("tt"), [])

    def test_removal_hints_for_brew_and_unknown(self):
        def copy(info: DetectedInstallInfo):
            return path_copies.CommandCopy("/x/tt", "/x/tt", info)

        self.assertEqual(
            path_copies.removal_hint(copy({"method": "brew_cask", "detail": "c"})),
            "brew uninstall --cask c",
        )
        self.assertEqual(
            path_copies.removal_hint(copy({"method": "brew_formula", "detail": "f"})),
            "brew uninstall f",
        )
        self.assertIsNone(
            path_copies.removal_hint(copy({"method": "script", "detail": None}))
        )


class TestNpmHandlersTargetActivePrefix(unittest.TestCase):
    """npm upgrade/remove name the prefix owning the copy that runs."""

    def test_upgrade_and_remove_pass_prefix(self):
        with tempfile.TemporaryDirectory() as td:
            prefix = os.path.join(os.path.realpath(td), "brew")
            bin_dir = _npm_install(prefix)
            with (
                mock.patch.dict(os.environ, {"PATH": bin_dir}),
                mock.patch.object(cli_handlers, "run_command") as mock_run,
            ):
                cli_handlers._upgrade_npm("tt", TOOL, "tt-pkg")
                cli_handlers._remove_npm("tt", TOOL, "tt-pkg")
        self.assertEqual(
            [c.args[0] for c in mock_run.call_args_list],
            [
                ["npm", "install", "-g", "--prefix", prefix, "tt-pkg@latest"],
                ["npm", "uninstall", "-g", "--prefix", prefix, "tt-pkg"],
            ],
        )


class TestRemoveWarnsAboutRemainingCopies(unittest.TestCase):
    """remove_tool reports copies of the command left on PATH."""

    def test_remaining_copy_is_reported_with_hint(self):
        remaining = path_copies.CommandCopy(
            "/opt/homebrew/bin/tt",
            "/opt/homebrew/lib/node_modules/tt-pkg/bin/tt.mjs",
            {"method": "npm", "detail": "tt-pkg"},
        )
        with (
            mock.patch.object(cli_operations, "TOOLS", {"tt": TOOL}),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=True),
            mock.patch.object(
                cli_operations,
                "detect_install_method",
                return_value={"method": "npm", "detail": "tt-pkg"},
            ),
            mock.patch.dict(
                cli_operations.REMOVE_HANDLERS,
                {cli_operations.InstallMethod.NPM: lambda *_: True},
            ),
            mock.patch.object(
                cli_operations, "find_command_copies", return_value=[remaining]
            ),
            mock.patch.object(cli_operations, "warning") as mock_warning,
            mock.patch.object(cli_operations, "info") as mock_info,
        ):
            self.assertTrue(cli_operations.remove_tool("tt"))
            mock_warning.reset_mock()
            self.assertTrue(cli_operations.remove_tool("tt", warn_remaining=False))
            mock_warning.assert_not_called()

        self.assertIn(
            "npm uninstall -g --prefix /opt/homebrew tt-pkg",
            " ".join(str(c.args[0]) for c in mock_info.call_args_list),
        )


if __name__ == "__main__":
    unittest.main()

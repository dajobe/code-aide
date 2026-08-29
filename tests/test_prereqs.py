"""Unit tests for prerequisite checking and Node.js installation."""

import subprocess
import unittest
from types import SimpleNamespace
from unittest import mock

from code_aide import constants
from code_aide import prereqs as cli_prereqs


def _fake_manager(**overrides):
    """Build a stand-in for a PackageManager with attribute access."""
    base = {
        "install_command": ["sudo", "apt-get", "install", "-y"],
        "pre_install": [],
        "packages": ["nodejs", "npm"],
        "detect_command": "apt-get",
        "description": "apt",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestInstallNodejsNpm(unittest.TestCase):
    """Tests for install_nodejs_npm."""

    def test_returns_false_when_no_package_manager(self):
        with mock.patch.object(
            cli_prereqs, "detect_package_manager", return_value=None
        ):
            self.assertFalse(cli_prereqs.install_nodejs_npm())

    def test_returns_false_when_npm_missing_after_install(self):
        with (
            mock.patch.object(
                cli_prereqs, "detect_package_manager", return_value=_fake_manager()
            ),
            mock.patch.object(cli_prereqs, "run_command"),
            mock.patch.object(cli_prereqs, "command_exists", return_value=False),
        ):
            self.assertFalse(cli_prereqs.install_nodejs_npm())

    def test_returns_true_on_success(self):
        with (
            mock.patch.object(
                cli_prereqs, "detect_package_manager", return_value=_fake_manager()
            ),
            mock.patch.object(cli_prereqs, "run_command"),
            mock.patch.object(cli_prereqs, "command_exists", return_value=True),
        ):
            self.assertTrue(cli_prereqs.install_nodejs_npm())

    def test_runs_pre_install_commands(self):
        mgr = _fake_manager(pre_install=[("sudo", "apt-get", "update")])
        with (
            mock.patch.object(cli_prereqs, "detect_package_manager", return_value=mgr),
            mock.patch.object(cli_prereqs, "run_command") as mock_run,
            mock.patch.object(cli_prereqs, "command_exists", return_value=True),
        ):
            cli_prereqs.install_nodejs_npm()
        # Pre-install command + install command = 2 calls
        self.assertEqual(mock_run.call_count, 2)
        first_args = mock_run.call_args_list[0][0][0]
        self.assertEqual(first_args, ["sudo", "apt-get", "update"])

    def test_returns_false_on_called_process_error(self):
        exc = subprocess.CalledProcessError(1, ["apt-get"], stderr="error")
        with (
            mock.patch.object(
                cli_prereqs, "detect_package_manager", return_value=_fake_manager()
            ),
            mock.patch.object(cli_prereqs, "run_command", side_effect=exc),
        ):
            self.assertFalse(cli_prereqs.install_nodejs_npm())

    def test_returns_false_on_generic_exception(self):
        with (
            mock.patch.object(
                cli_prereqs, "detect_package_manager", return_value=_fake_manager()
            ),
            mock.patch.object(
                cli_prereqs, "run_command", side_effect=RuntimeError("boom")
            ),
        ):
            self.assertFalse(cli_prereqs.install_nodejs_npm())


class TestCheckPrerequisites(unittest.TestCase):
    """Tests for check_prerequisites."""

    def test_freebsd_port_skips_npm_check(self):
        tool_config = {"name": "Test", "command": "test", "freebsd_port": "net/test"}
        with (
            mock.patch.object(cli_prereqs.platform, "system", return_value="FreeBSD"),
            mock.patch.dict(constants._TOOLS_DATA, {"test": tool_config}, clear=True),
            mock.patch.object(cli_prereqs, "command_exists") as mock_exists,
        ):
            cli_prereqs.check_prerequisites(["test"])
        # npm not even probed because FreeBSD port short-circuits
        mock_exists.assert_not_called()

    def test_npm_required_but_missing_exits_when_no_install_prereqs(self):
        tool_config = {"name": "Test", "command": "test", "prerequisites": ["npm"]}
        with (
            mock.patch.object(cli_prereqs.platform, "system", return_value="Linux"),
            mock.patch.dict(constants._TOOLS_DATA, {"test": tool_config}, clear=True),
            mock.patch.object(cli_prereqs, "command_exists", return_value=False),
        ):
            with self.assertRaises(SystemExit):
                cli_prereqs.check_prerequisites(["test"], install_prereqs=False)

    def test_npm_required_install_prereqs_failure_exits(self):
        tool_config = {"name": "Test", "command": "test", "prerequisites": ["npm"]}
        with (
            mock.patch.object(cli_prereqs.platform, "system", return_value="Linux"),
            mock.patch.dict(constants._TOOLS_DATA, {"test": tool_config}, clear=True),
            mock.patch.object(cli_prereqs, "command_exists", return_value=False),
            mock.patch.object(cli_prereqs, "install_nodejs_npm", return_value=False),
        ):
            with self.assertRaises(SystemExit):
                cli_prereqs.check_prerequisites(["test"], install_prereqs=True)

    def test_npm_present_no_install_attempted(self):
        tool_config = {"name": "Test", "command": "test", "prerequisites": ["npm"]}
        completed = subprocess.CompletedProcess(
            ["npm", "--version"], 0, stdout="10.0.0\n", stderr=""
        )
        with (
            mock.patch.object(cli_prereqs.platform, "system", return_value="Linux"),
            mock.patch.dict(constants._TOOLS_DATA, {"test": tool_config}, clear=True),
            mock.patch.object(cli_prereqs, "command_exists", return_value=True),
            mock.patch.object(cli_prereqs, "run_command", return_value=completed),
            mock.patch.object(cli_prereqs, "install_nodejs_npm") as mock_install,
        ):
            cli_prereqs.check_prerequisites(["test"], install_prereqs=True)
        mock_install.assert_not_called()

    def test_node_version_too_low_exits(self):
        tool_config = {
            "name": "Test",
            "command": "test",
            "prerequisites": [],
            "min_node_version": 20,
        }
        completed = subprocess.CompletedProcess(
            ["node", "--version"], 0, stdout="v18.0.0\n", stderr=""
        )
        with (
            mock.patch.object(cli_prereqs.platform, "system", return_value="Linux"),
            mock.patch.dict(constants._TOOLS_DATA, {"test": tool_config}, clear=True),
            mock.patch.object(cli_prereqs, "run_command", return_value=completed),
        ):
            with self.assertRaises(SystemExit):
                cli_prereqs.check_prerequisites(["test"], install_prereqs=False)

    def test_node_version_check_failure_exits(self):
        tool_config = {
            "name": "Test",
            "command": "test",
            "prerequisites": [],
            "min_node_version": 20,
        }
        with (
            mock.patch.object(cli_prereqs.platform, "system", return_value="Linux"),
            mock.patch.dict(constants._TOOLS_DATA, {"test": tool_config}, clear=True),
            mock.patch.object(
                cli_prereqs,
                "run_command",
                side_effect=subprocess.CalledProcessError(1, ["node"]),
            ),
        ):
            with self.assertRaises(SystemExit):
                cli_prereqs.check_prerequisites(["test"], install_prereqs=False)

    def test_npm_version_probe_missing_binary_exits_cleanly(self):
        tool_config = {"name": "Test", "command": "test", "prerequisites": ["npm"]}
        with (
            mock.patch.object(cli_prereqs.platform, "system", return_value="Linux"),
            mock.patch.dict(constants._TOOLS_DATA, {"test": tool_config}, clear=True),
            mock.patch.object(cli_prereqs, "command_exists", return_value=True),
            mock.patch.object(
                cli_prereqs, "run_command", side_effect=FileNotFoundError("npm")
            ),
        ):
            with self.assertRaises(SystemExit):
                cli_prereqs.check_prerequisites(["test"], install_prereqs=False)

    def test_node_missing_binary_exits_cleanly(self):
        tool_config = {
            "name": "Test",
            "command": "test",
            "min_node_version": 20,
        }
        with (
            mock.patch.object(cli_prereqs.platform, "system", return_value="Linux"),
            mock.patch.dict(constants._TOOLS_DATA, {"test": tool_config}, clear=True),
            mock.patch.object(
                cli_prereqs, "run_command", side_effect=FileNotFoundError("node")
            ),
        ):
            with self.assertRaises(SystemExit):
                cli_prereqs.check_prerequisites(["test"], install_prereqs=False)

    def test_unknown_tool_skipped(self):
        with (
            mock.patch.object(cli_prereqs.platform, "system", return_value="Linux"),
            mock.patch.dict(constants._TOOLS_DATA, {}, clear=True),
        ):
            # Should not raise; simply skips unknown tool
            cli_prereqs.check_prerequisites(["nonexistent"])


class TestIsToolInstalled(unittest.TestCase):
    """Tests for is_tool_installed."""

    def test_known_tool_returns_true_when_present(self):
        tool_config = {"name": "Test", "command": "test"}
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"test": tool_config}, clear=True),
            mock.patch.object(cli_prereqs, "command_exists", return_value=True),
        ):
            self.assertTrue(cli_prereqs.is_tool_installed("test"))

    def test_known_tool_returns_false_when_absent(self):
        tool_config = {"name": "Test", "command": "test"}
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"test": tool_config}, clear=True),
            mock.patch.object(cli_prereqs, "command_exists", return_value=False),
        ):
            self.assertFalse(cli_prereqs.is_tool_installed("test"))

    def test_unknown_tool_returns_false(self):
        with mock.patch.dict(constants._TOOLS_DATA, {}, clear=True):
            self.assertFalse(cli_prereqs.is_tool_installed("totally_unknown"))


class TestCheckPathDirectories(unittest.TestCase):
    """Tests for check_path_directories."""

    def test_warns_when_existing_bin_dir_not_in_path(self):
        with (
            mock.patch.dict("os.environ", {"PATH": "/usr/bin"}, clear=False),
            mock.patch.object(cli_prereqs.os.path, "isdir", return_value=True),
            mock.patch("builtins.print") as mock_print,
        ):
            cli_prereqs.check_path_directories(["/custom/bin"])
        # Should have printed at least the bin dir as a warning detail
        printed = " ".join(
            str(call.args[0]) for call in mock_print.call_args_list if call.args
        )
        self.assertIn("/custom/bin", printed)

    def test_silent_when_dir_already_in_path(self):
        with (
            mock.patch.dict(
                "os.environ", {"PATH": "/custom/bin:/usr/bin"}, clear=False
            ),
            mock.patch.object(cli_prereqs.os.path, "isdir", return_value=True),
            mock.patch("builtins.print") as mock_print,
        ):
            cli_prereqs.check_path_directories(["/custom/bin"])
        self.assertFalse(mock_print.called)

    def test_silent_when_bin_dir_does_not_exist(self):
        with (
            mock.patch.dict("os.environ", {"PATH": "/usr/bin"}, clear=False),
            mock.patch.object(cli_prereqs.os.path, "isdir", return_value=False),
            mock.patch("builtins.print") as mock_print,
        ):
            cli_prereqs.check_path_directories(["/missing/bin"])
        self.assertFalse(mock_print.called)


if __name__ == "__main__":
    unittest.main()

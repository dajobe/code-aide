"""Error-path tests for operations.upgrade_tool / remove_tool / install."""

import subprocess
import unittest
from unittest import mock

from code_aide import constants
from code_aide import install as cli_install
from code_aide import operations as cli_operations
from code_aide import operation_handlers as cli_handlers
from code_aide.operations import UpgradeResult


class TestUpgradeToolErrorPaths(unittest.TestCase):
    """Error branches in operations.upgrade_tool."""

    def test_unknown_tool_returns_failed(self):
        with mock.patch.dict(constants._TOOLS_DATA, {}, clear=True):
            self.assertEqual(
                cli_operations.upgrade_tool("nonexistent"), UpgradeResult.FAILED
            )

    def test_not_installed_returns_failed(self):
        cfg = {"name": "Test", "command": "test", "install_type": "script"}
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"test": cfg}, clear=True),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=False),
        ):
            self.assertEqual(cli_operations.upgrade_tool("test"), UpgradeResult.FAILED)

    def test_unknown_install_method_returns_failed(self):
        cfg = {"name": "Test", "command": "test", "install_type": "script"}
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"test": cfg}, clear=True),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=True),
            mock.patch.object(
                cli_operations, "is_deprecated_install", return_value=False
            ),
            mock.patch.object(
                cli_operations,
                "detect_install_method",
                return_value={"method": None, "detail": None},
            ),
            mock.patch.object(
                cli_operations,
                "_get_upgrade_snapshot",
                return_value={"method": None, "detail": None, "version": None},
            ),
        ):
            self.assertEqual(cli_operations.upgrade_tool("test"), UpgradeResult.FAILED)

    def test_npm_method_without_package_returns_failed(self):
        cfg = {"name": "Test", "command": "test", "install_type": "npm"}
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"test": cfg}, clear=True),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=True),
            mock.patch.object(
                cli_operations, "is_deprecated_install", return_value=False
            ),
            mock.patch.object(
                cli_operations,
                "detect_install_method",
                return_value={"method": "npm", "detail": None},
            ),
            mock.patch.object(
                cli_operations,
                "_get_upgrade_snapshot",
                return_value={"method": "npm", "detail": None, "version": None},
            ),
        ):
            self.assertEqual(cli_operations.upgrade_tool("test"), UpgradeResult.FAILED)

    def test_pkg_method_without_port_returns_failed(self):
        cfg = {"name": "Test", "command": "test", "install_type": "script"}
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"test": cfg}, clear=True),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=True),
            mock.patch.object(
                cli_operations, "is_deprecated_install", return_value=False
            ),
            mock.patch.object(
                cli_operations,
                "detect_install_method",
                return_value={"method": "pkg", "detail": None},
            ),
            mock.patch.object(
                cli_operations,
                "_get_upgrade_snapshot",
                return_value={"method": "pkg", "detail": None, "version": None},
            ),
        ):
            self.assertEqual(cli_operations.upgrade_tool("test"), UpgradeResult.FAILED)

    def test_system_method_is_not_upgradable(self):
        cfg = {"name": "Test", "command": "test", "install_type": "script"}
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"test": cfg}, clear=True),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=True),
            mock.patch.object(
                cli_operations, "is_deprecated_install", return_value=False
            ),
            mock.patch.object(
                cli_operations,
                "detect_install_method",
                return_value={"method": "system", "detail": "/usr/bin/test"},
            ),
            mock.patch.object(
                cli_operations,
                "_get_upgrade_snapshot",
                return_value={
                    "method": "system",
                    "detail": "/usr/bin/test",
                    "version": None,
                },
            ),
        ):
            self.assertEqual(cli_operations.upgrade_tool("test"), UpgradeResult.FAILED)

    def test_subprocess_error_returns_failed(self):
        cfg = {
            "name": "Test",
            "command": "test",
            "install_type": "npm",
            "npm_package": "@test/cli",
        }
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"test": cfg}, clear=True),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=True),
            mock.patch.object(
                cli_operations, "is_deprecated_install", return_value=False
            ),
            mock.patch.object(
                cli_operations,
                "detect_install_method",
                return_value={"method": "npm", "detail": "@test/cli"},
            ),
            mock.patch.object(
                cli_operations,
                "_get_upgrade_snapshot",
                return_value={
                    "method": "npm",
                    "detail": "@test/cli",
                    "version": None,
                },
            ),
            mock.patch.object(
                cli_handlers,
                "run_command",
                side_effect=subprocess.CalledProcessError(1, ["npm"], stderr="boom"),
            ),
        ):
            self.assertEqual(cli_operations.upgrade_tool("test"), UpgradeResult.FAILED)


class TestRemoveToolErrorPaths(unittest.TestCase):
    """Error branches in operations.remove_tool."""

    def test_unknown_tool_returns_false(self):
        with mock.patch.dict(constants._TOOLS_DATA, {}, clear=True):
            self.assertFalse(cli_operations.remove_tool("nonexistent"))

    def test_not_installed_returns_true(self):
        cfg = {"name": "Test", "command": "test"}
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"test": cfg}, clear=True),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=False),
        ):
            self.assertTrue(cli_operations.remove_tool("test"))

    def test_unknown_method_returns_false(self):
        cfg = {"name": "Test", "command": "test"}
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"test": cfg}, clear=True),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=True),
            mock.patch.object(
                cli_operations,
                "detect_install_method",
                return_value={"method": None, "detail": None},
            ),
        ):
            self.assertFalse(cli_operations.remove_tool("test"))

    def test_npm_without_package_returns_false(self):
        cfg = {"name": "Test", "command": "test"}
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"test": cfg}, clear=True),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=True),
            mock.patch.object(
                cli_operations,
                "detect_install_method",
                return_value={"method": "npm", "detail": None},
            ),
        ):
            self.assertFalse(cli_operations.remove_tool("test"))

    def test_pkg_without_port_returns_false(self):
        cfg = {"name": "Test", "command": "test"}
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"test": cfg}, clear=True),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=True),
            mock.patch.object(
                cli_operations,
                "detect_install_method",
                return_value={"method": "pkg", "detail": None},
            ),
        ):
            self.assertFalse(cli_operations.remove_tool("test"))

    def test_system_method_not_removable(self):
        cfg = {"name": "Test", "command": "test"}
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"test": cfg}, clear=True),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=True),
            mock.patch.object(
                cli_operations,
                "detect_install_method",
                return_value={"method": "system", "detail": "/usr/bin/test"},
            ),
        ):
            self.assertFalse(cli_operations.remove_tool("test"))

    def test_script_remove_no_binary_returns_true_with_warning(self):
        cfg = {"name": "Test", "command": "test", "install_type": "script"}
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"test": cfg}, clear=True),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=True),
            mock.patch.object(
                cli_operations,
                "detect_install_method",
                return_value={"method": "script", "detail": None},
            ),
            mock.patch.object(cli_handlers.shutil, "which", return_value=None),
        ):
            # No binary found, should warn but succeed.
            self.assertTrue(cli_operations.remove_tool("test"))

    def test_script_remove_permission_error_then_sudo_failure(self):
        cfg = {"name": "Test", "command": "test", "install_type": "script"}
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"test": cfg}, clear=True),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=True),
            mock.patch.object(
                cli_operations,
                "detect_install_method",
                return_value={"method": "script", "detail": None},
            ),
            mock.patch.object(
                cli_handlers.shutil, "which", return_value="/usr/local/bin/test"
            ),
            mock.patch.object(
                cli_handlers.os, "remove", side_effect=PermissionError("denied")
            ),
            mock.patch.object(
                cli_handlers,
                "run_command",
                side_effect=subprocess.CalledProcessError(1, ["sudo"], stderr="nope"),
            ),
        ):
            self.assertFalse(cli_operations.remove_tool("test"))

    def test_script_remove_os_remove_generic_error(self):
        cfg = {"name": "Test", "command": "test", "install_type": "script"}
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"test": cfg}, clear=True),
            mock.patch.object(cli_operations, "is_tool_installed", return_value=True),
            mock.patch.object(
                cli_operations,
                "detect_install_method",
                return_value={"method": "script", "detail": None},
            ),
            mock.patch.object(
                cli_handlers.shutil, "which", return_value="/usr/local/bin/test"
            ),
            mock.patch.object(
                cli_handlers.os, "remove", side_effect=OSError("disk full")
            ),
        ):
            self.assertFalse(cli_operations.remove_tool("test"))


class TestInstallErrorPaths(unittest.TestCase):
    """Error branches in install.run_install_script and install_direct_download."""

    def test_run_install_script_sha256_mismatch_returns_false(self):
        with mock.patch.object(
            cli_install, "fetch_url", return_value=(b"#!/bin/bash\n", None)
        ):
            self.assertFalse(
                cli_install.run_install_script(
                    "https://example/install.sh",
                    "test",
                    expected_sha256="0" * 64,
                )
            )

    def test_detect_os_arch_unsupported_os(self):
        with mock.patch.object(cli_install.platform, "system", return_value="Plan9"):
            with self.assertRaises(RuntimeError) as cm:
                cli_install.detect_os_arch()
            self.assertIn("Unsupported OS", str(cm.exception))

    def test_detect_os_arch_unsupported_machine(self):
        with (
            mock.patch.object(cli_install.platform, "system", return_value="Linux"),
            mock.patch.object(cli_install.platform, "machine", return_value="riscv"),
        ):
            with self.assertRaises(RuntimeError) as cm:
                cli_install.detect_os_arch()
            self.assertIn("Unsupported architecture", str(cm.exception))

    def test_install_direct_download_unsupported_os_returns_false(self):
        cfg = {
            "name": "Test",
            "command": "test",
            "download_url_template": "https://example/{version}-{os}-{arch}.tar.gz",
            "install_dir": "~/.local/test-{version}",
            "bin_dir": "~/.local/bin",
            "latest_version": "1.0.0",
        }
        with (
            mock.patch.dict(constants._TOOLS_DATA, {"test": cfg}, clear=True),
            mock.patch.object(
                cli_install,
                "detect_os_arch",
                side_effect=RuntimeError("Unsupported OS: plan9"),
            ),
        ):
            self.assertFalse(cli_install.install_direct_download("test", cfg))


if __name__ == "__main__":
    unittest.main()

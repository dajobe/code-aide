"""Unit tests for the package_managers module."""

import subprocess
import unittest
from unittest import mock

from code_aide.package_managers import (
    PACKAGE_MANAGER_BY_ENUM,
    PackageManager,
    _MANAGERS,
    _parse_package_name,
    detect_package_manager,
    query_package_owner,
)


class TestPackageManagerEnum(unittest.TestCase):
    """Tests for the PackageManager enum."""

    def test_all_managers_have_entries(self):
        for mgr in PackageManager:
            self.assertIn(mgr, PACKAGE_MANAGER_BY_ENUM)

    def test_manager_list_matches_enum(self):
        managers_in_list = {info.manager for info in _MANAGERS}
        self.assertEqual(managers_in_list, set(PackageManager))

    def test_no_duplicate_detect_commands(self):
        commands = [info.detect_command for info in _MANAGERS]
        self.assertEqual(len(commands), len(set(commands)))


class TestPackageManagerInfo(unittest.TestCase):
    """Tests for PackageManagerInfo completeness."""

    def test_all_managers_have_install_command(self):
        for info in _MANAGERS:
            self.assertTrue(
                len(info.install_command) > 0,
                f"{info.manager.name} missing install_command",
            )

    def test_all_managers_have_query_owner_command(self):
        for info in _MANAGERS:
            self.assertTrue(
                len(info.query_owner_command) > 0,
                f"{info.manager.name} missing query_owner_command",
            )

    def test_all_managers_have_remove_command(self):
        for info in _MANAGERS:
            self.assertTrue(
                len(info.remove_command) > 0,
                f"{info.manager.name} missing remove_command",
            )

    def test_all_managers_have_description(self):
        for info in _MANAGERS:
            self.assertTrue(
                len(info.description) > 0,
                f"{info.manager.name} missing description",
            )

    def test_all_managers_have_packages(self):
        for info in _MANAGERS:
            self.assertTrue(
                len(info.packages) > 0,
                f"{info.manager.name} missing packages",
            )

    def test_info_is_frozen(self):
        info = PACKAGE_MANAGER_BY_ENUM[PackageManager.APT]
        with self.assertRaises(AttributeError):
            info.description = "changed"


class TestDetectPackageManager(unittest.TestCase):
    """Tests for detect_package_manager."""

    @mock.patch("code_aide.package_managers.platform.system", return_value="Windows")
    def test_returns_none_on_windows(self, _mock_sys):
        self.assertIsNone(detect_package_manager())

    @mock.patch("code_aide.package_managers.shutil.which", return_value=None)
    @mock.patch("code_aide.package_managers.platform.system", return_value="Linux")
    def test_returns_none_when_no_manager_found(self, _mock_sys, _mock_which):
        self.assertIsNone(detect_package_manager())

    @mock.patch("code_aide.package_managers.shutil.which")
    @mock.patch("code_aide.package_managers.platform.system", return_value="Linux")
    def test_detects_apt(self, _mock_sys, mock_which):
        mock_which.side_effect = lambda cmd: (
            "/usr/bin/apt-get" if cmd == "apt-get" else None
        )
        result = detect_package_manager()
        self.assertIsNotNone(result)
        self.assertEqual(result.manager, PackageManager.APT)

    @mock.patch("code_aide.package_managers.shutil.which")
    @mock.patch("code_aide.package_managers.platform.system", return_value="Linux")
    def test_detects_emerge(self, _mock_sys, mock_which):
        mock_which.side_effect = lambda cmd: (
            "/usr/bin/emerge" if cmd == "emerge" else None
        )
        result = detect_package_manager()
        self.assertIsNotNone(result)
        self.assertEqual(result.manager, PackageManager.EMERGE)

    @mock.patch("code_aide.package_managers.shutil.which")
    @mock.patch("code_aide.package_managers.platform.system", return_value="FreeBSD")
    def test_detects_pkg_on_freebsd(self, _mock_sys, mock_which):
        mock_which.side_effect = lambda cmd: "/usr/sbin/pkg" if cmd == "pkg" else None
        result = detect_package_manager()
        self.assertIsNotNone(result)
        self.assertEqual(result.manager, PackageManager.PKG)

    @mock.patch("code_aide.package_managers.shutil.which")
    @mock.patch("code_aide.package_managers.platform.system", return_value="Darwin")
    def test_detects_brew_on_macos(self, _mock_sys, mock_which):
        mock_which.side_effect = lambda cmd: (
            "/opt/homebrew/bin/brew" if cmd == "brew" else None
        )
        result = detect_package_manager()
        self.assertIsNotNone(result)
        self.assertEqual(result.manager, PackageManager.HOMEBREW)

    @mock.patch("code_aide.package_managers.shutil.which")
    @mock.patch("code_aide.package_managers.platform.system", return_value="Linux")
    def test_returns_first_match(self, _mock_sys, mock_which):
        # apt-get is first in the list
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}"
        result = detect_package_manager()
        self.assertEqual(result.manager, PackageManager.APT)


class TestParsePackageName(unittest.TestCase):
    """Tests for _parse_package_name output parsing."""

    def test_apt_dpkg_output(self):
        self.assertEqual(
            _parse_package_name(PackageManager.APT, "libfoo:amd64: /usr/lib/libfoo.so"),
            "libfoo",
        )

    def test_apt_simple_output(self):
        self.assertEqual(
            _parse_package_name(PackageManager.APT, "claude-code: /usr/bin/claude"),
            "claude-code",
        )

    def test_dnf_rpm_output(self):
        self.assertEqual(
            _parse_package_name(PackageManager.DNF, "claude-code-2.1.50-1.x86_64"),
            "claude-code-2.1.50-1.x86_64",
        )

    def test_pacman_output(self):
        self.assertEqual(
            _parse_package_name(
                PackageManager.PACMAN,
                "/usr/bin/claude is owned by claude-code 2.1.50",
            ),
            "claude-code",
        )

    def test_pacman_no_match(self):
        self.assertIsNone(
            _parse_package_name(PackageManager.PACMAN, "error: no package"),
        )

    def test_emerge_output(self):
        self.assertEqual(
            _parse_package_name(PackageManager.EMERGE, "dev-util/claude-code"),
            "dev-util/claude-code",
        )

    def test_pkg_output(self):
        self.assertEqual(
            _parse_package_name(PackageManager.PKG, "claude-code-2.1.50"),
            "claude-code-2.1.50",
        )

    def test_brew_output(self):
        self.assertEqual(
            _parse_package_name(PackageManager.HOMEBREW, "gemini-cli"),
            "gemini-cli",
        )

    def test_empty_output(self):
        self.assertIsNone(_parse_package_name(PackageManager.APT, ""))
        self.assertIsNone(_parse_package_name(PackageManager.APT, "\n"))

    def test_multiline_takes_first(self):
        self.assertEqual(
            _parse_package_name(PackageManager.EMERGE, "dev-util/foo\ndev-util/bar"),
            "dev-util/foo",
        )


class TestQueryPackageOwner(unittest.TestCase):
    """Tests for query_package_owner."""

    @mock.patch("code_aide.package_managers.detect_package_manager", return_value=None)
    def test_returns_none_when_no_manager(self, _mock):
        pkg, cmd = query_package_owner("/usr/bin/example")
        self.assertIsNone(pkg)
        self.assertIsNone(cmd)

    @mock.patch("code_aide.package_managers.subprocess.run")
    @mock.patch("code_aide.package_managers.detect_package_manager")
    def test_emerge_query(self, mock_detect, mock_run):
        mock_detect.return_value = PACKAGE_MANAGER_BY_ENUM[PackageManager.EMERGE]
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="dev-util/claude-code\n"
        )
        pkg, cmd = query_package_owner("/opt/bin/claude")
        self.assertEqual(pkg, "dev-util/claude-code")
        self.assertEqual(cmd, "sudo emerge --unmerge dev-util/claude-code")
        mock_run.assert_called_once_with(
            ["qfile", "-qC", "/opt/bin/claude"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            stdin=subprocess.DEVNULL,
        )

    @mock.patch("code_aide.package_managers.subprocess.run")
    @mock.patch("code_aide.package_managers.detect_package_manager")
    def test_apt_query(self, mock_detect, mock_run):
        mock_detect.return_value = PACKAGE_MANAGER_BY_ENUM[PackageManager.APT]
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="claude-code: /usr/bin/claude\n"
        )
        pkg, cmd = query_package_owner("/usr/bin/claude")
        self.assertEqual(pkg, "claude-code")
        self.assertEqual(cmd, "sudo apt-get remove claude-code")

    @mock.patch("code_aide.package_managers.subprocess.run")
    @mock.patch("code_aide.package_managers.detect_package_manager")
    def test_brew_uses_basename(self, mock_detect, mock_run):
        mock_detect.return_value = PACKAGE_MANAGER_BY_ENUM[PackageManager.HOMEBREW]
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="gemini-cli\n"
        )
        pkg, cmd = query_package_owner("/opt/homebrew/bin/gemini")
        self.assertEqual(pkg, "gemini-cli")
        self.assertEqual(cmd, "brew uninstall gemini-cli")
        # Verify basename was passed, not full path
        mock_run.assert_called_once_with(
            ["brew", "which-formula", "gemini"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            stdin=subprocess.DEVNULL,
        )

    @mock.patch("code_aide.package_managers.subprocess.run")
    @mock.patch("code_aide.package_managers.detect_package_manager")
    def test_returns_none_on_query_failure(self, mock_detect, mock_run):
        mock_detect.return_value = PACKAGE_MANAGER_BY_ENUM[PackageManager.APT]
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout=""
        )
        pkg, cmd = query_package_owner("/usr/bin/example")
        self.assertIsNone(pkg)
        self.assertIsNone(cmd)

    @mock.patch("code_aide.package_managers.subprocess.run")
    @mock.patch("code_aide.package_managers.detect_package_manager")
    def test_returns_none_on_exception(self, mock_detect, mock_run):
        mock_detect.return_value = PACKAGE_MANAGER_BY_ENUM[PackageManager.APT]
        mock_run.side_effect = OSError("timeout")
        pkg, cmd = query_package_owner("/usr/bin/example")
        self.assertIsNone(pkg)
        self.assertIsNone(cmd)

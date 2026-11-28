"""Tests for restoring files an install script modifies."""

import os
import tempfile
import unittest
from unittest import mock

from code_aide import install as cli_install
from code_aide.preserved_files import get_install_preserve_files, preserved_files


def _read(path):
    with open(path, "rb") as handle:
        return handle.read()


def _write(path, data):
    with open(path, "wb") as handle:
        handle.write(data)


class TestPreservedFiles(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.home = self._td.name

    def tearDown(self):
        self._td.cleanup()

    def path(self, *parts):
        return os.path.join(self.home, *parts)

    def test_appended_regular_file_is_restored(self):
        profile = self.path(".profile")
        _write(profile, b"original\n")
        os.chmod(profile, 0o600)

        with preserved_files([profile]):
            with open(profile, "ab") as handle:
                handle.write(b'export PATH="$HOME/.local/bin:$PATH"\n')
            os.chmod(profile, 0o644)

        self.assertEqual(_read(profile), b"original\n")
        self.assertEqual(os.stat(profile).st_mode & 0o777, 0o600)

    def test_unchanged_file_is_not_rewritten(self):
        profile = self.path(".bashrc")
        _write(profile, b"original\n")
        os.utime(profile, (1_000_000, 1_000_000))

        with preserved_files([profile]):
            pass

        self.assertEqual(os.stat(profile).st_mtime, 1_000_000)

    def test_symlink_target_edit_is_restored(self):
        dotfiles = self.path("dotfiles")
        os.mkdir(dotfiles)
        target = os.path.join(dotfiles, "bash_profile")
        _write(target, b"from dotfiles\n")
        link = self.path(".bash_profile")
        os.symlink(target, link)

        with preserved_files([link]):
            with open(link, "ab") as handle:
                handle.write(b"# Added by installer\n")

        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.readlink(link), target)
        self.assertEqual(_read(target), b"from dotfiles\n")

    def test_symlink_replaced_by_file_is_relinked(self):
        dotfiles = self.path("dotfiles")
        os.mkdir(dotfiles)
        target = os.path.join(dotfiles, "zshrc")
        _write(target, b"from dotfiles\n")
        link = self.path(".zshrc")
        os.symlink(target, link)

        with preserved_files([link]):
            os.remove(link)
            _write(link, b"from dotfiles\n# Added by installer\n")

        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.readlink(link), target)
        self.assertEqual(_read(target), b"from dotfiles\n")

    def test_created_file_and_directories_are_removed(self):
        os.mkdir(self.path(".config"))
        fish = self.path(".config", "fish", "config.fish")

        with preserved_files([fish]):
            os.makedirs(os.path.dirname(fish))
            _write(fish, b"fish_add_path ~/.local/bin\n")

        self.assertFalse(os.path.lexists(fish))
        self.assertFalse(os.path.lexists(self.path(".config", "fish")))
        self.assertTrue(os.path.isdir(self.path(".config")))

    def test_tilde_paths_expand_against_home(self):
        profile = self.path(".zprofile")
        _write(profile, b"original\n")

        with mock.patch.dict(os.environ, {"HOME": self.home}):
            with preserved_files(["~/.zprofile"]):
                _write(profile, b"changed\n")

        self.assertEqual(_read(profile), b"original\n")

    def test_restores_when_block_raises(self):
        profile = self.path(".profile")
        _write(profile, b"original\n")

        with self.assertRaises(KeyboardInterrupt):
            with preserved_files([profile]):
                _write(profile, b"changed\n")
                raise KeyboardInterrupt

        self.assertEqual(_read(profile), b"original\n")

    def test_get_preserve_files_absent(self):
        self.assertIsNone(get_install_preserve_files({}))


class TestRunInstallScriptPreservesFiles(unittest.TestCase):
    @mock.patch.object(cli_install, "fetch_url")
    def test_script_profile_edit_is_reverted(self, mock_fetch):
        with tempfile.TemporaryDirectory() as home:
            profile = os.path.join(home, ".profile")
            _write(profile, b"original\n")
            script = f"echo 'export PATH=x' >> '{profile}'\n".encode()
            mock_fetch.return_value = (script, None)

            with mock.patch.dict(os.environ, {"HOME": home}):
                result = cli_install.run_install_script(
                    "https://example.com/install.sh",
                    "Example",
                    cli_install.hashlib.sha256(script).hexdigest(),
                    preserve_files=["~/.profile"],
                )

            self.assertTrue(result)
            self.assertEqual(_read(profile), b"original\n")


if __name__ == "__main__":
    unittest.main()

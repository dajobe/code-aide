"""Tests for install script replacements."""

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from code_aide import install as cli_install
from code_aide.script_patches import (
    apply_script_replacements,
    get_install_script_replacements,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_JSON = REPO_ROOT / "src" / "code_aide" / "data" / "tools.json"
ARCHIVE_DIR = REPO_ROOT / "script-archive"


class TestApplyScriptReplacements(unittest.TestCase):
    def test_no_replacements_returns_content_unchanged(self):
        self.assertEqual(apply_script_replacements(b"echo hi\n", None), b"echo hi\n")
        self.assertEqual(apply_script_replacements(b"echo hi\n", []), b"echo hi\n")

    def test_replaces_every_occurrence(self):
        script = b'"$B" install --dir x || true\n"$B" install || true\n'
        result = apply_script_replacements(
            script, [{"old": '"$B" install', "new": '"$B" install --skip-path'}]
        )
        self.assertEqual(
            result,
            b'"$B" install --skip-path --dir x || true\n'
            b'"$B" install --skip-path || true\n',
        )

    def test_missing_old_string_raises(self):
        with self.assertRaises(ValueError):
            apply_script_replacements(b"echo hi\n", [{"old": "nope", "new": "x"}])

    def test_get_replacements_absent(self):
        self.assertIsNone(get_install_script_replacements({}))


class TestRunInstallScriptReplacements(unittest.TestCase):
    @mock.patch.object(cli_install, "fetch_url")
    @mock.patch.object(cli_install.subprocess, "Popen")
    def test_replaced_script_is_executed_after_verification(
        self, mock_popen, mock_fetch
    ):
        script = b"agy install\n"
        process = mock.Mock()
        process.communicate.return_value = (b"", b"")
        process.returncode = 0
        mock_popen.return_value = process
        mock_fetch.return_value = (script, None)

        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict(os.environ, {"HOME": home}):
                result = cli_install.run_install_script(
                    "https://example.com/install.sh",
                    "Example",
                    hashlib.sha256(script).hexdigest(),
                    replacements=[
                        {"old": "agy install", "new": "agy install --skip-path"}
                    ],
                )

        self.assertTrue(result)
        process.communicate.assert_called_once_with(input=b"agy install --skip-path\n")

    @mock.patch.object(cli_install, "fetch_url")
    @mock.patch.object(cli_install.subprocess, "Popen")
    def test_unmatched_replacement_does_not_run_script(self, mock_popen, mock_fetch):
        script = b"echo hi\n"
        mock_fetch.return_value = (script, None)

        result = cli_install.run_install_script(
            "https://example.com/install.sh",
            "Example",
            hashlib.sha256(script).hexdigest(),
            replacements=[{"old": "agy install", "new": "x"}],
        )

        self.assertFalse(result)
        mock_popen.assert_not_called()


class TestBundledReplacementsMatchArchive(unittest.TestCase):
    """Each bundled replacement must apply to the archived install script."""

    def test_antigravity_skips_shell_profile_edits(self):
        tools = json.loads(TOOLS_JSON.read_text())["tools"]
        cfg = tools["antigravity"]
        script = (ARCHIVE_DIR / "antigravity-install.sh").read_bytes()
        self.assertEqual(hashlib.sha256(script).hexdigest(), cfg["install_sha256"])

        patched = apply_script_replacements(
            script, get_install_script_replacements(cfg)
        ).decode("utf-8")

        install_calls = [
            line.strip()
            for line in patched.splitlines()
            if line.strip().startswith('"$BINARY_PATH" install')
        ]
        self.assertEqual(len(install_calls), 2)
        for line in install_calls:
            self.assertIn("--skip-path", line)
            self.assertIn("--skip-aliases", line)


if __name__ == "__main__":
    unittest.main()

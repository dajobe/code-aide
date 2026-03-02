"""Unit tests for shared CLI constants."""

import unittest

from code_aide import constants as cli_constants


class TestClaudeScriptConfig(unittest.TestCase):
    """Tests for claude tool config expectations."""

    def test_claude_install_type_is_script(self):
        self.assertEqual(cli_constants.TOOLS["claude"]["install_type"], "script")

    def test_claude_has_no_prerequisites(self):
        self.assertEqual(cli_constants.TOOLS["claude"].get("prerequisites", []), [])

    def test_claude_has_install_url(self):
        self.assertIn("install_url", cli_constants.TOOLS["claude"])

    def test_claude_has_install_sha256(self):
        self.assertIn("install_sha256", cli_constants.TOOLS["claude"])

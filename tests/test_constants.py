"""Unit tests for shared CLI constants."""

import os
import unittest
from unittest import mock

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


class TestLazyColors(unittest.TestCase):
    """Colors resolve lazily from the environment, not at import time."""

    def setUp(self):
        cli_constants._color_state["enabled"] = None

    def test_force_color_enables_codes_after_import(self):
        env = {k: v for k, v in os.environ.items() if k != "NO_COLOR"}
        env["FORCE_COLOR"] = "1"
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertNotEqual(cli_constants.Colors.GREEN, "")
            self.assertNotEqual(cli_constants.Colors.NC, "")

    def test_no_color_disables_codes_after_import(self):
        with mock.patch.dict(os.environ, {"NO_COLOR": "1"}):
            self.assertEqual(cli_constants.Colors.GREEN, "")

    def test_unknown_color_attribute_raises(self):
        with self.assertRaises(AttributeError):
            cli_constants.Colors.MAGENTA

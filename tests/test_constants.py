"""Unit tests for shared CLI constants."""

import unittest

from code_aide import constants as cli_constants


class TestSelfManagedConfig(unittest.TestCase):
    """Tests for self-managed tool config expectations."""

    def test_claude_install_still_requires_npm(self):
        self.assertEqual(cli_constants.TOOLS["claude"]["install_type"], "self_managed")
        self.assertIn("npm", cli_constants.TOOLS["claude"].get("prerequisites", []))

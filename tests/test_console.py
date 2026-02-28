"""Unit tests for console helpers."""

import subprocess
import unittest
from unittest import mock

from code_aide import console


class TestConsoleFormatting(unittest.TestCase):
    """Tests for prefixed console output functions."""

    @mock.patch("builtins.print")
    def test_info_prefix(self, mock_print):
        console.info("hello")
        output = mock_print.call_args[0][0]
        self.assertIn("[INFO]", output)
        self.assertIn("hello", output)

    @mock.patch("builtins.print")
    def test_error_prefix(self, mock_print):
        console.error("boom")
        output = mock_print.call_args[0][0]
        self.assertIn("[ERROR]", output)
        self.assertIn("boom", output)


class TestConsoleExecution(unittest.TestCase):
    """Tests for command_exists and run_command."""

    @mock.patch.object(console.shutil, "which", return_value="/usr/bin/tool")
    def test_command_exists_true(self, _mock_which):
        self.assertTrue(console.command_exists("tool"))

    @mock.patch.object(console.shutil, "which", return_value=None)
    def test_command_exists_false(self, _mock_which):
        self.assertFalse(console.command_exists("tool"))

    def test_run_command_check_false_returns_exception(self):
        err = subprocess.CalledProcessError(1, ["cmd"], output="o", stderr="e")
        with mock.patch.object(console.subprocess, "run", side_effect=err):
            result = console.run_command(["cmd"], check=False)
        self.assertIs(result, err)

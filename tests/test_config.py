"""Unit tests for config module."""

import os
import tempfile
import unittest
from unittest import mock

from code_aide import config as code_aide_config


class TestGetConfigDir(unittest.TestCase):
    """Tests for config.get_config_dir."""

    def test_respects_xdg_config_home(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": td}):
                config_dir = code_aide_config.get_config_dir()
                self.assertEqual(config_dir, os.path.join(td, "code-aide"))
                self.assertTrue(os.path.isdir(config_dir))

    def test_defaults_to_home_config(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": "", "HOME": td}):
                env = os.environ.copy()
                env.pop("XDG_CONFIG_HOME", None)
                with mock.patch.dict(os.environ, env, clear=True):
                    config_dir = code_aide_config.get_config_dir()
                    self.assertIn("code-aide", config_dir)


class TestLoadBundledTools(unittest.TestCase):
    """Tests for config.load_bundled_tools."""

    def test_returns_valid_tool_definitions(self):
        bundled = code_aide_config.load_bundled_tools()
        self.assertIn("tools", bundled)
        tools = bundled["tools"]
        self.assertIn("claude", tools)
        self.assertIn("copilot", tools)
        self.assertIn("gemini", tools)
        self.assertIn("opencode", tools)
        self.assertIn("kilo", tools)
        for tool_name, tool_data in tools.items():
            self.assertIn("name", tool_data)
            self.assertIn("command", tool_data)
            self.assertIn("install_type", tool_data)


class TestVersionsCacheRoundTrip(unittest.TestCase):
    """Tests for config save/load versions cache."""

    def test_save_then_load_works(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": td}):
                test_data = {
                    "tools": {
                        "claude": {
                            "latest_version": "9.9.9",
                            "latest_date": "2026-12-31",
                        }
                    }
                }
                code_aide_config.save_versions_cache(test_data)
                loaded = code_aide_config.load_versions_cache()
                self.assertEqual(loaded, test_data)

    def test_load_returns_empty_when_no_cache(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": td}):
                os.makedirs(os.path.join(td, "code-aide"), exist_ok=True)
                loaded = code_aide_config.load_versions_cache()
                self.assertEqual(loaded, {})

    def test_load_returns_empty_on_invalid_json(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": td}):
                cache_dir = os.path.join(td, "code-aide")
                os.makedirs(cache_dir, exist_ok=True)
                cache_path = os.path.join(cache_dir, "versions.json")
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write("{invalid")
                loaded = code_aide_config.load_versions_cache()
                self.assertEqual(loaded, {})


class TestMergeCachedOverBundled(unittest.TestCase):
    """Tests for config.load_tools_config merge behavior."""

    def test_cached_data_takes_precedence(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": td}):
                cache_data = {
                    "tools": {
                        "claude": {
                            "latest_version": "99.0.0",
                            "latest_date": "2099-01-01",
                        }
                    }
                }
                code_aide_config.save_versions_cache(cache_data)

                tools = code_aide_config.load_tools_config()
                self.assertEqual(tools["claude"]["latest_version"], "99.0.0")
                self.assertEqual(tools["claude"]["latest_date"], "2099-01-01")
                self.assertEqual(tools["claude"]["install_type"], "script")


if __name__ == "__main__":
    unittest.main()

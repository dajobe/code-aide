"""Unit tests for config module."""

import json
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
        self.assertIn("antigravity", tools)
        self.assertIn("opencode", tools)
        self.assertIn("kilo", tools)
        for tool_name, tool_data in tools.items():
            self.assertIn("name", tool_data)
            self.assertIn("command", tool_data)
            self.assertIn("install_type", tool_data)


class TestAntigravityConfig(unittest.TestCase):
    """Antigravity remains separate from the supported Gemini CLI entry."""

    def test_antigravity_uses_verified_script_and_manifest(self):
        tools = code_aide_config.load_bundled_tools()["tools"]
        antigravity = tools["antigravity"]

        self.assertEqual(antigravity["command"], "agy")
        self.assertIn("agy", antigravity["aliases"])
        self.assertEqual(antigravity["install_type"], "script")
        self.assertIn("install_sha256", antigravity)
        self.assertIn("version_manifest_url_template", antigravity)
        self.assertTrue(antigravity["self_updates"])
        self.assertTrue(antigravity["default_install"])

    def test_gemini_remains_available_but_is_not_default(self):
        gemini = code_aide_config.load_bundled_tools()["tools"]["gemini"]

        self.assertEqual(gemini["command"], "gemini")
        self.assertFalse(gemini["default_install"])

    def test_cursor_remains_available_but_is_not_default(self):
        cursor = code_aide_config.load_bundled_tools()["tools"]["cursor"]

        self.assertEqual(cursor["command"], "agent")
        self.assertFalse(cursor["default_install"])


class TestResolveToolNames(unittest.TestCase):
    """Tool aliases resolve without creating duplicate catalog entries."""

    def test_resolves_alias_to_canonical_name(self):
        tools = {
            "antigravity": {"aliases": ["agy"]},
            "gemini": {},
        }
        self.assertEqual(
            code_aide_config.resolve_tool_names(["agy"], tools),
            ["antigravity"],
        )

    def test_resolves_command_name_alias(self):
        tools = {"cursor": {"aliases": ["agent"]}}
        self.assertEqual(
            code_aide_config.resolve_tool_names(["agent"], tools),
            ["cursor"],
        )

    def test_deduplicates_alias_and_canonical_name(self):
        tools = {"antigravity": {"aliases": ["agy"]}}
        self.assertEqual(
            code_aide_config.resolve_tool_names(["agy", "antigravity"], tools),
            ["antigravity"],
        )

    def test_preserves_unknown_name_for_validation(self):
        self.assertEqual(
            code_aide_config.resolve_tool_names(["missing"], {}),
            ["missing"],
        )


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

    def test_save_creates_directory_and_leaves_no_temp_files(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": td}):
                code_aide_config.save_versions_cache({"tools": {}})
                cache_dir = os.path.join(td, "code-aide")
                cache_path = os.path.join(cache_dir, "versions.json")
                self.assertTrue(os.path.isfile(cache_path))
                with open(cache_path, encoding="utf-8") as f:
                    self.assertEqual(json.load(f), {"tools": {}})
                self.assertEqual(os.listdir(cache_dir), ["versions.json"])


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


class TestMergeInstallSha256DirectDownload(unittest.TestCase):
    """install_sha256 from cache must not apply to direct_download tools."""

    def test_merge_skips_install_sha256_for_direct_download(self):
        tools = {
            "cursor": {
                "install_type": "direct_download",
                "name": "Cursor CLI",
                "command": "agent",
            }
        }
        cache = {
            "tools": {
                "cursor": {
                    "latest_version": "2026.03.11-6dfa30c",
                    "install_sha256": "7ccf2992a4de12c040854a833db0255a08cdfc91d40c75b78cf66a8746d9bd24",
                }
            }
        }
        code_aide_config.merge_cached_versions(tools, cache)
        self.assertEqual(tools["cursor"]["latest_version"], "2026.03.11-6dfa30c")
        self.assertNotIn("install_sha256", tools["cursor"])

    def test_save_omits_install_sha256_for_direct_download(self):
        tools = {
            "cursor": {
                "install_type": "direct_download",
                "name": "Cursor CLI",
                "latest_version": "1.0.0",
                "install_sha256": "should_not_persist",
            }
        }
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": td}):
                code_aide_config.save_updated_versions(tools)
                loaded = code_aide_config.load_versions_cache()
        entry = loaded["tools"]["cursor"]
        self.assertEqual(entry["latest_version"], "1.0.0")
        self.assertNotIn("install_sha256", entry)


class TestMergeInstallSha256StaleCacheIgnored(unittest.TestCase):
    """Stale cached install_sha256 must not override updated bundled hash."""

    def test_bundled_sha256_wins_over_stale_cache(self):
        tools = {
            "amp": {
                "install_type": "script",
                "name": "Amp",
                "command": "amp",
                "install_sha256": "new_bundled_hash_from_release",
            }
        }
        cache = {
            "tools": {
                "amp": {
                    "install_sha256": "old_cached_hash",
                }
            }
        }
        code_aide_config.merge_cached_versions(tools, cache)
        self.assertEqual(
            tools["amp"]["install_sha256"], "new_bundled_hash_from_release"
        )

    def test_cache_applies_when_bundled_sha256_absent(self):
        tools = {
            "amp": {
                "install_type": "script",
                "name": "Amp",
                "command": "amp",
            }
        }
        cache = {
            "tools": {
                "amp": {
                    "install_sha256": "cached_hash",
                }
            }
        }
        code_aide_config.merge_cached_versions(tools, cache)
        self.assertEqual(tools["amp"]["install_sha256"], "cached_hash")

    def test_cache_applies_when_sha256_matches_bundled(self):
        tools = {
            "amp": {
                "install_type": "script",
                "name": "Amp",
                "command": "amp",
                "install_sha256": "same_hash",
            }
        }
        cache = {
            "tools": {
                "amp": {
                    "install_sha256": "same_hash",
                }
            }
        }
        code_aide_config.merge_cached_versions(tools, cache)
        self.assertEqual(tools["amp"]["install_sha256"], "same_hash")


class TestDownloadSha256Scoping(unittest.TestCase):
    """download_sha256 from cache applies only to direct_download tools."""

    def test_merge_skips_download_sha256_for_npm_tools(self):
        tools = {
            "gemini": {"install_type": "npm", "name": "Gemini", "command": "gemini"}
        }
        cache = {"tools": {"gemini": {"download_sha256": "a" * 64}}}
        code_aide_config.merge_cached_versions(tools, cache)
        self.assertNotIn("download_sha256", tools["gemini"])

    def test_merge_applies_download_sha256_for_direct_download(self):
        tools = {
            "cursor": {
                "install_type": "direct_download",
                "name": "Cursor CLI",
                "command": "agent",
            }
        }
        cache = {"tools": {"cursor": {"download_sha256": "b" * 64}}}
        code_aide_config.merge_cached_versions(tools, cache)
        self.assertEqual(tools["cursor"]["download_sha256"], "b" * 64)

    def test_save_omits_download_sha256_for_non_direct_tools(self):
        tools = {
            "gemini": {
                "install_type": "npm",
                "name": "Gemini",
                "latest_version": "1.0.0",
                "download_sha256": "should_not_persist",
            }
        }
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": td}):
                code_aide_config.save_updated_versions(tools)
                loaded = code_aide_config.load_versions_cache()
        entry = loaded["tools"]["gemini"]
        self.assertEqual(entry["latest_version"], "1.0.0")
        self.assertNotIn("download_sha256", entry)


if __name__ == "__main__":
    unittest.main()

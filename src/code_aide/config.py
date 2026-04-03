"""Configuration management for code-aide.

Handles XDG base directory paths, loading bundled tool definitions from
package data, loading/saving the user's version cache, and merging
bundled defaults with cached data.
"""

import importlib.resources
import json
import os
import time

from code_aide.install_types import InstallType, parse_install_type


def get_config_dir() -> str:
    """Return XDG config directory for code-aide.

    Uses $XDG_CONFIG_HOME/code-aide if set, else ~/.config/code-aide.
    Creates the directory if it doesn't exist.
    """
    xdg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    config_dir = os.path.join(xdg, "code-aide")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


def get_versions_cache_path() -> str:
    """Return path to the user's version cache file."""
    return os.path.join(get_config_dir(), "versions.json")


def load_bundled_tools() -> dict:
    """Load static tool definitions bundled with the package.

    Uses importlib.resources to read src/code_aide/data/tools.json.
    """
    ref = importlib.resources.files("code_aide").joinpath("data/tools.json")
    with importlib.resources.as_file(ref) as path:
        with open(path) as f:
            return json.load(f)


def load_versions_cache() -> dict:
    """Load the user's cached version data, or empty dict if none."""
    cache_path = get_versions_cache_path()
    if os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    return {}


def save_versions_cache(data: dict) -> None:
    """Write version data to the user's cache file."""
    cache_path = get_versions_cache_path()
    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


# Cache is considered stale after 24 hours.
CACHE_MAX_AGE_SECONDS = 86400

DYNAMIC_FIELDS = ["latest_version", "latest_date", "install_sha256"]


def merge_cached_versions(tools: dict, cache: dict) -> None:
    """Merge cached dynamic fields into tool definitions in-place.

    For install_sha256, the bundled value takes precedence when it differs
    from the cache, since a new release with an updated hash means the
    cache is stale.
    """
    cached_tools = cache.get("tools", {})
    for tool_key, tool_data in tools.items():
        if tool_key in cached_tools:
            for field in DYNAMIC_FIELDS:
                if field in cached_tools[tool_key]:
                    if field == "install_sha256":
                        install_type = parse_install_type(tool_data.get("install_type"))
                        if install_type == InstallType.DIRECT_DOWNLOAD:
                            # Script checksum does not apply to tarball installs;
                            # ignore stale cache from older releases.
                            continue
                        bundled_sha = tool_data.get("install_sha256")
                        cached_sha = cached_tools[tool_key][field]
                        if bundled_sha and cached_sha and bundled_sha != cached_sha:
                            # Bundled hash was updated in a newer release;
                            # discard stale cached hash.
                            continue
                    tool_data[field] = cached_tools[tool_key][field]


def load_tools_config() -> dict:
    """Load tool config: bundled definitions merged with cached versions.

    Two-layer model: the bundled tools.json provides tool definitions and
    install_sha256 checksums (for script-type tools). The user's version
    cache (from update-versions) provides latest_version, latest_date,
    and updated install_sha256 values when present. Cached install_sha256
    is ignored for direct_download tools (tarball installs).
    """
    bundled = load_bundled_tools()
    cache = load_versions_cache()
    tools = bundled.get("tools", {})
    merge_cached_versions(tools, cache)
    return tools


def save_updated_versions(tools: dict) -> None:
    """Save only dynamic version fields to the user's cache.

    Called by update-versions command. Only stores latest_version,
    latest_date, and install_sha256 per tool.
    """
    cache_data = {"tools": {}}
    for tool_key, tool_data in tools.items():
        entry = {}
        for field in DYNAMIC_FIELDS:
            if field in tool_data:
                if (
                    field == "install_sha256"
                    and parse_install_type(tool_data.get("install_type"))
                    == InstallType.DIRECT_DOWNLOAD
                ):
                    continue
                entry[field] = tool_data[field]
        if entry:
            cache_data["tools"][tool_key] = entry
    save_versions_cache(cache_data)


def versions_cache_is_fresh(tools: dict) -> bool:
    """Return True if the versions cache exists, is recent, and complete."""
    cache_path = get_versions_cache_path()
    try:
        age = time.time() - os.path.getmtime(cache_path)
        if age >= CACHE_MAX_AGE_SECONDS:
            return False
    except OSError:
        return False

    # Check that every versionable tool has latest_version populated.
    for tool_config in tools.values():
        install_type = parse_install_type(tool_config.get("install_type"))
        if install_type == InstallType.NPM:
            if not tool_config.get("latest_version"):
                return False
        elif install_type in (InstallType.SCRIPT, InstallType.DIRECT_DOWNLOAD):
            if tool_config.get("version_url") and not tool_config.get("latest_version"):
                return False
    return True


def refresh_versions_cache(tools: dict) -> None:
    """Fetch latest versions from upstream and update tools dict in-place.

    Called automatically by status commands when the cache is missing or
    stale.  Only updates latest_version and latest_date (not install_sha256).
    """
    # Import here to avoid circular dependency (versions imports constants
    # which imports config).
    from code_aide.versions import (
        check_npm_tool,
        check_script_tool,
        normalize_version,
    )

    for name, tool_config in tools.items():
        install_type = parse_install_type(tool_config.get("install_type"))
        try:
            if install_type == InstallType.NPM:
                result = check_npm_tool(name, tool_config)
            elif install_type in (InstallType.SCRIPT, InstallType.DIRECT_DOWNLOAD):
                if "install_url" not in tool_config:
                    continue
                result = check_script_tool(name, tool_config)
            else:
                continue
        except Exception:
            continue

        if result["status"] == "error":
            continue

        version = result.get("version", "-")
        if version and version != "-":
            tool_config["latest_version"] = normalize_version(version)
        date = result.get("date", "-")
        if date and date != "-":
            tool_config["latest_date"] = date

    save_updated_versions(tools)


def ensure_versions_cache(tools: dict) -> None:
    """Refresh versions cache if missing, stale, or incomplete."""
    if not versions_cache_is_fresh(tools):
        refresh_versions_cache(tools)

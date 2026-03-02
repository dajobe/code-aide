# Remove bundled version baseline

## Context

code-aide has a three-layer version data model where `latest_version` and
`latest_date` are bundled in `tools.json` as a baseline. These go stale
between releases and require a manual release step (`update-versions -b
-y`). The `install_sha256` field protects against tampered install scripts
and must remain bundled.

## Approach

Remove `latest_version` and `latest_date` from bundled data and the
`-b`/`--bundled` flag from `update-versions`, simplifying to two layers:
bundled definitions (with SHA256) + user cache (with versions). The
`install_direct_download()` function needs an on-demand fetch when
`latest_version` is missing (fresh install with no cache).

## Changes

### 1. `src/code_aide/data/tools.json` -- remove version fields

Remove `latest_version` and `latest_date` from all 8 tool entries. Keep
`install_sha256`.

### 2. `src/code_aide/config.py` -- remove bundled save function

- Remove `save_bundled_versions()` function.
- Update `load_tools_config()` docstring to describe two-layer model.
- `DYNAMIC_FIELDS` stays the same (user cache still stores all three).

### 3. `src/code_aide/entry.py` -- remove --bundled flag

Remove `-b`/`--bundled` argument from the update-versions subparser.

### 4. `src/code_aide/commands_actions.py` -- simplify update-versions

- Remove `save_bundled_versions` from imports.
- Remove `if not args.bundled:` guard around `merge_cached_versions` --
  always merge.
- Remove bundled branch in `_save()` -- always save to user cache.
- Remove `args.bundled` reference.

### 5. `src/code_aide/install.py` -- handle missing latest_version

In `install_direct_download()`, `tool_config["latest_version"]` will
KeyError on fresh installs with no cache. Add on-demand fetch: if
`latest_version` is missing, call `check_script_tool()` to get it before
proceeding with the download.

### 6. `README.md` -- update documentation

- Rewrite "How Version Data Works" to describe two-layer model.
- Remove release step 1 (`update-versions -b -y` step).
- Remove usage example for `update-versions -b -y`.

### 7. `AGENTS.md` -- update layer description

Change "Three-layer version data" to "Two-layer version data" and update
description.

### 8. Tests

- `tests/test_commands_actions.py`: Remove
  `test_bundled_flag_skips_cache_and_saves_to_bundled`. Update remaining
  tests that set `"bundled": False` in args.

## Verification

1. `pre-commit run --all-files` -- formatting passes
2. `uv run pytest tests/ -v` -- all tests pass
3. `uv run python -m code_aide status` -- shows versions from cache, or
   plain version without comparison if no cache
4. `uv run python -m code_aide update-versions -n` -- fetches latest
   versions
5. `uv run python -m code_aide update-versions -y` -- saves to user cache
6. `uv run python -m code_aide update-versions -b` -- errors (flag removed)

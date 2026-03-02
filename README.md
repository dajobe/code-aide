# code-aide

An aide for your AI coding tools.

Manages installation, upgrade, removal, and version tracking of AI coding
CLI tools: Claude Code, Copilot, Cursor, Gemini, Amp, Codex, OpenCode, and
Kilo.

## Installation

```bash
# Run without installing (requires uv)
uvx code-aide status

# Install persistently
uv tool install code-aide

# Or use pipx
pipx install code-aide
```

## Usage

```bash
# List available tools and their status
code-aide list

# Show detailed status for installed tools
code-aide status

# Install specific tools
code-aide install claude gemini

# Install all default tools
code-aide install

# Install with automatic prerequisite installation (Node.js, npm)
code-aide install -p

# Upgrade installed tools (no args = only out-of-date tools)
code-aide upgrade [NAMES]

# Remove tools
code-aide remove [NAMES]

# Check upstream for latest versions (dry-run)
code-aide update-versions -n

# Update version cache
code-aide update-versions -y
```

## Supported Tools

| Tool                     | Command   | Install Type       | Default |
|--------------------------|-----------|--------------------|---------|
| Cursor CLI               | `agent`   | Direct download    | Yes     |
| Claude CLI (Claude Code) | `claude`  | Script             | Yes     |
| Gemini CLI               | `gemini`  | npm                | Yes     |
| OpenCode                 | `opencode`| npm                | No      |
| Kilo CLI                 | `kilo`    | npm                | No      |
| Amp (Sourcegraph)        | `amp`     | Script             | No      |
| Codex CLI                | `codex`   | npm                | No      |
| Copilot CLI              | `copilot` | npm                | No      |

## How Version Data Works

code-aide uses a two-layer version data model:

1. **Bundled tool definitions** (in `data/tools.json`): Install methods,
   URLs, npm packages, version args, and SHA256 checksums. Updated by
   releasing new versions of code-aide.

2. **User's local version cache** (`~/.config/code-aide/versions.json`):
   Written by `code-aide update-versions`. Provides latest versions, dates,
   and updated SHA256 checksums.

Run `code-aide update-versions` to get the latest version data without
waiting for a new code-aide release.

## Features

- Zero external dependencies (Python stdlib only)
- SHA256 verification for script-based installations
- Automatic prerequisite detection and installation (Node.js, npm)
- Detects install method (Homebrew, npm, system package, script, direct
  download)
- PATH configuration validation and warnings
- Supports Linux and macOS

## Requirements

- Python 3.11+
- No external Python dependencies

## Development

1. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Install dependencies: `uv sync`
3. Install pre-commit hooks: `uv tool install pre-commit && pre-commit
   install`
4. Run tests: `uv run pytest tests/ -v`

```bash
# Run from development checkout
uv run python -m code_aide status
uv run python -m code_aide install copilot

# Run a specific test
uv run pytest tests/test_install.py::TestDetectOsArch -v
```

## Release

`publish.yml` publishes to PyPI when a Git tag matching `v*` is pushed.

1. Update the version string in `src/code_aide/__init__.py` (`__version__`).
   `pyproject.toml` reads it automatically via Hatchling.
2. Run checks:
   - `uv run pytest tests/ -v`
   - `uv build`
3. Commit the release version bump:
   - `git add src/code_aide/__init__.py`
   - `git commit -m "Bumped version to X.Y.Z"`
4. Write useful commit messages before tagging:
   - Start subject lines with an action verb in past tense (`Added`,
     `Changed`, `Fixed`, `Removed`).
   - Keep subjects user-facing so auto-generated release notes are
     meaningful.
   - Group related changes into focused commits instead of one broad commit.
   - Example: `Fixed timeout handling in status command`
5. Tag and push:
   - `git tag vX.Y.Z`
   - `git push origin main --follow-tags`
6. Confirm GitHub Actions:
   - CI should pass.
   - Publish workflow should upload to PyPI and create GitHub Release notes.
   - Release notes should include generated notes plus a commit summary from
     the previous tag to the current tag.

## License

Apache-2.0

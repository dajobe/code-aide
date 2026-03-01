# code-aide

An aide for your AI coding tools.

Manages installation, upgrade, removal, and version tracking of AI coding CLI
tools: Claude Code, Copilot, Cursor, Gemini, Amp, Codex, OpenCode, and Kilo.

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

# Update bundled version baseline (developer use, before releases)
code-aide update-versions -b -y
```

## Supported Tools

| Tool                     | Command   | Install Type       | Default |
|--------------------------|------------|--------------------|---------|
| Cursor CLI               | `agent`    | Direct download    | Yes     |
| Claude CLI (Claude Code) | `claude`   | Self-managed (npm) | Yes     |
| Gemini CLI               | `gemini`   | npm                | Yes     |
| OpenCode                  | `opencode`| npm                | No      |
| Kilo CLI                  | `kilo`    | npm                | No      |
| Amp (Sourcegraph)        | `amp`      | Script             | No      |
| Codex CLI                 | `codex`   | npm                | No      |
| Copilot CLI               | `copilot` | npm                | No      |

## How Version Data Works

code-aide uses a three-layer version data model:

1. **Tool definitions** (bundled with the package): Install methods, URLs, npm
   packages, version args. Updated by releasing new versions of code-aide.

2. **Bundled version baseline** (in `data/tools.json`): Latest versions and
   SHA256 hashes as known at release time. Acts as a fallback for fresh
   installs.

3. **User's local version cache** (`~/.config/code-aide/versions.json`): Written
   by `code-aide update-versions`. Takes precedence over bundled data when
   present.

Run `code-aide update-versions` to get fresher version data without waiting for
a new code-aide release.

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

```bash
# Run from development checkout
uv run python -m code_aide status
uv run python -m code_aide install copilot

# Run tests
uv run pytest tests/ -v

# Run a specific test
uv run pytest tests/test_install.py::TestDetectOsArch -v
```

## Release

`publish.yml` publishes to PyPI when a Git tag matching `v*` is pushed.

1. Update the bundled version baseline:
   - `code-aide update-versions -b -y`
   - `git add src/code_aide/data/tools.json`
   - `git commit -m "Updated bundled version data"`
2. Update the version string in `src/code_aide/__init__.py` (`__version__`).
   `pyproject.toml` reads it automatically via Hatchling.
3. Run checks:
   - `uv run pytest tests/ -v`
   - `uv build`
4. Commit the release version bump:
   - `git add src/code_aide/__init__.py`
   - `git commit -m "Bumped version to X.Y.Z"`
5. Write useful commit messages before tagging:
   - Start subject lines with an action verb in past tense (`Added`, `Changed`,
     `Fixed`, `Removed`).
   - Keep subjects user-facing so auto-generated release notes are meaningful.
   - Group related changes into focused commits instead of one broad commit.
   - Example: `Fixed timeout handling in status command`
6. Tag and push:
   - `git tag vX.Y.Z`
   - `git push origin main --follow-tags`
7. Confirm GitHub Actions:
   - CI should pass.
   - Publish workflow should upload to PyPI and create GitHub Release notes.
   - Release notes should include generated notes plus a commit summary from the
     previous tag to the current tag.

## License

Apache-2.0

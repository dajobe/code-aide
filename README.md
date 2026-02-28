# code-aide

An aide for your AI coding tools.

Manages installation, upgrade, removal, and version tracking of AI coding CLI
tools: Claude Code, Cursor, Gemini, Amp, and Codex.

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

# Upgrade installed tools
code-aide upgrade [NAMES]

# Remove tools
code-aide remove [NAMES]

# Check upstream for latest versions (dry-run)
code-aide update-versions -n

# Update version cache
code-aide update-versions -y
```

## Supported Tools

| Tool                     | Command  | Install Type       | Default |
|--------------------------|----------|--------------------|---------|
| Cursor CLI               | `agent`  | Direct download    | Yes     |
| Claude CLI (Claude Code) | `claude` | Self-managed (npm) | Yes     |
| Gemini CLI               | `gemini` | npm                | Yes     |
| Amp (Sourcegraph)        | `amp`    | Script             | No      |
| Codex CLI                | `codex`  | npm                | No      |

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
# Run tests
uv run pytest tests/ -v

# Run a specific test
uv run pytest tests/test_install.py::TestDetectOsArch -v
```

## License

Apache-2.0

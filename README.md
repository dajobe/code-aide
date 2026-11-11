# code-aide

An aide for your AI coding tools.

Manages installation, upgrade, removal, and version tracking of AI coding CLI
tools: Claude Code, Antigravity, Copilot, Cursor, Gemini, Amp, Codex, OpenCode,
Kilo, and T3 Code.

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
# Show compact one-line-per-tool status (default when no command is given)
code-aide

# List available tools and their status
code-aide list

# Show compact one-line-per-tool status
code-aide status

# Show detailed status for installed tools
code-aide status -l

# Install specific tools
code-aide install claude antigravity

# Install all default tools
code-aide install

# Install with automatic prerequisite installation (Node.js, npm)
code-aide install -p

# Verify checksums and show what would be installed, without installing
code-aide install -n

# Upgrade installed tools (no args = only out-of-date tools)
code-aide upgrade [NAMES]

# Remove tools (prompts before removing all managed tools)
code-aide remove [NAMES]

# Preview a removal without changing anything
code-aide remove -n

# Remove all managed tools without prompting
code-aide remove -y

# Remove stale version directories of direct-download tools
code-aide clean [NAMES]

# Check upstream for latest versions (dry-run)
code-aide update-versions -n

# Update version cache
code-aide update-versions -y
```

## Supported Tools

| Tool                        | Command    | Install Type    | Default |
|:----------------------------|:-----------|:----------------|:--------|
| Cursor CLI                  | `agent`    | Direct download | No      |
| Claude CLI (Claude Code)    | `claude`   | Script          | Yes     |
| Antigravity CLI             | `agy`      | Script          | Yes     |
| Gemini CLI                  | `gemini`   | npm             | No      |
| OpenCode                    | `opencode` | npm             | No      |
| Kilo CLI                    | `kilo`     | npm             | No      |
| Amp (Sourcegraph)           | `amp`      | Script          | No      |
| Codex CLI                   | `codex`    | npm             | No      |
| Copilot CLI                 | `copilot`  | npm             | No      |
| T3 Code                     | `t3`       | Direct download | No      |
| T3 Code desktop app (macOS) | (app)      | App bundle      | No      |

Command aliases are also accepted: `agy` resolves to `antigravity`, `agent` to
`cursor`, and `t3` to `t3code`.

T3 Code installs the `t3` command from the GitHub release tarball, verified
against the release's `SHA256SUMS`, into `~/.t3/runtime/versions/` (the same
layout as the upstream installer). There is no `t3` command for Intel Macs; use
the desktop app there (`brew install --cask t3-code`). code-aide never restarts
the `t3` background service; after the CLI changes version it reminds you to run
`t3 service restart`. A `t3` command provided by the desktop app is reported as
a Homebrew cask install when the `t3-code` cask owns the app.

On macOS, `t3code-app` installs the T3 Code desktop app. Each release's signed
zip is checked against the SHA-512 in the release's `latest-mac.yml`, unpacked
into `~/.local/opt/t3code-app/v<version>/`, and activated by pointing
`~/Applications/T3 Code.app` at it. The CLI and the app upgrade together:
upgrading either one also upgrades the other if it is installed, so both run the
same release. If the app is running, code-aide offers to quit it before
switching versions; if it stays running, neither is upgraded. `status` warns
when the two versions differ.

## How Version Data Works

code-aide uses a two-layer version data model:

1. **Bundled tool definitions** (in `data/tools.json`): Install methods, URLs,
   npm packages, version args, and SHA256 checksums. Updated by releasing new
   versions of code-aide.

2. **User's local version cache** (`~/.config/code-aide/versions.json`): Written
   by `code-aide update-versions`. Provides latest versions, dates, updated
   SHA256 checksums, and recorded tarball checksums for direct_download tools.

Run `code-aide update-versions` to get the latest version data without waiting
for a new code-aide release.

## Tool definition schema (`data/tools.json`)

Each entry in `tools.json` describes one managed tool. Required fields are
`name`, `command`, and `install_type`; the others are optional and only
consulted when the relevant install method or platform applies.

| Field                            | Required | Notes                                                                                                                |
|:---------------------------------|:---------|:---------------------------------------------------------------------------------------------------------------------|
| `name`                           | Yes      | Display name for status output                                                                                       |
| `command`                        | Yes      | Binary name (looked up in `PATH`)                                                                                    |
| `aliases`                        | No       | Alternate names accepted by commands and resolved to the canonical tool key                                          |
| `install_type`                   | Yes      | One of `npm`, `script`, `direct_download`, `pkg`, `app_bundle`                                                       |
| `version_args`                   | No       | List of arguments passed to the binary to print its version (default: `["--version"]`)                               |
| `version_url`                    | No       | URL queried by `update-versions` to discover the latest upstream version                                             |
| `version_manifest_url_template`  | No       | JSON manifest URL template with `{platform}`; reads its `version` field                                              |
| `version_extract_pattern`        | No       | Regex applied to the install script to extract the version before generic heuristics                                 |
| `github_release_repo`            | No       | `owner/repo` whose latest (non-prerelease) GitHub release supplies the version; replaces the install script check    |
| `latest_version`                 | Cache    | Last known upstream version (filled by `update-versions`)                                                            |
| `latest_date`                    | Cache    | Release date for `latest_version`                                                                                    |
| `prerequisites`                  | No       | List of required external commands (e.g. `["npm"]`)                                                                  |
| `min_node_version`               | No       | Minimum major Node.js version required                                                                               |
| `npm_package`                    | npm      | npm package name (e.g. `@anthropic-ai/claude-code`)                                                                  |
| `install_url`                    | script   | URL of the install script that will be downloaded and piped to `bash`                                                |
| `install_sha256`                 | script   | SHA-256 of the install script body — required for verified installs                                                  |
| `download_sha256`                | Cache    | SHA-256 of the downloaded tarball for direct_download tools; recorded by `update-versions`, verified on install      |
| `install_script_path_prepend`    | script   | Extra directories prepended to `PATH` when the install script runs (e.g. `["~/.local/bin"]`)                         |
| `macos_quarantine_paths`         | script   | Tool-owned paths for macOS quarantine cleanup; expands `~` and resolves executable symlinks                          |
| `download_url_template`          | direct   | URL template with `{version}`, `{os}`, `{arch}` placeholders                                                         |
| `install_dir`                    | direct   | Directory to extract into; supports `{version}`                                                                      |
| `bin_dir`                        | direct   | Directory where symlinks for `command` are created (e.g. `~/.local/bin`)                                             |
| `symlinks`                       | direct   | Map of `link_name` → relative path inside `install_dir` to symlink into `bin_dir`                                    |
| `checksums_url_template`         | direct   | Publisher `SHA256SUMS` URL template; verified on install in place of `download_sha256`                               |
| `unsupported_platforms`          | direct   | Map of `<os>-<arch>` to an explanation; install refuses those platforms                                              |
| `install_complete_marker`        | direct   | File written into the version directory, holding the version, after extraction; an existing match skips the download |
| `launcher_record_file`           | direct   | File that symlink paths are appended to, so the tool's own pruning keeps the linked version                          |
| `brew_cask`                      | No       | Homebrew cask that ships a desktop app providing `command`; used for detection and status hints                      |
| `desktop_cli_shim`               | No       | Path of the desktop app's CLI shim; a command resolving to it is detected as the app (or `brew_cask`)                |
| `desktop_cli_hint`               | No       | Status hint shown when `brew_cask` is installed but `command` is not                                                 |
| `freebsd_port`                   | FreeBSD  | FreeBSD ports/pkg name (used when running on FreeBSD)                                                                |
| `freebsd_pkg_repo`               | FreeBSD  | Optional non-default pkg repository name (passed via `pkg install -r <repo>`)                                        |
| `next_steps`                     | No       | Free-form text printed after a successful install                                                                    |
| `docs_url`                       | No       | Documentation URL printed after install                                                                              |
| `platforms`                      | No       | `platform.system().lower()` values (e.g. `["darwin"]`); the tool is hidden elsewhere                                 |
| `upgrade_with`                   | No       | Tools upgraded alongside this one, held back if it is not upgraded                                                   |
| `self_pruning_versions`          | No       | The tool prunes its own version directories; `clean` leaves them alone                                               |
| `service_files`                  | No       | Background service files; when one exists, `service_restart_hint` is shown after an upgrade                          |
| `service_restart_hint`           | No       | Message shown when a background service keeps running the previous version                                           |
| `app_link`                       | app      | Symlink that activates the installed app version (e.g. `~/Applications/T3 Code.app`)                                 |
| `app_bundle_name`                | app      | Bundle name inside each version directory and in the zip                                                             |
| `bundle_id`                      | app      | Bundle identifier, used to ask the running app to quit                                                               |
| `running_process_name`           | app      | Process name checked before switching or removing a version                                                          |
| `checksum_manifest_url_template` | app      | electron-builder `latest-mac.yml` URL template holding each zip's SHA-512                                            |
| `self_updates`                   | No       | Tool updates itself when run; excludes it from managed upgrade actions                                               |

## Features

- Zero external dependencies (Python stdlib only)
- SHA256 verification for script-based installations
- Automatic prerequisite detection and installation (Node.js, npm)
- Detects install method (Homebrew, npm, system package, script, direct
  download)
- PATH configuration validation and warnings
- Supports Linux and macOS

## Configuration

- Tool definitions are bundled at `src/code_aide/data/tools.json`.
- The version cache lives at `~/.config/code-aide/versions.json` by default; set
  `XDG_CONFIG_HOME` to relocate the `code-aide` config directory.
- Color output honors `NO_COLOR`, `FORCE_COLOR`, `CLICOLOR_FORCE`, `CLICOLOR=0`,
  and `TERM=dumb`, in that priority order; color is disabled when stdout is not
  a terminal.

## Requirements

- Python 3.11+
- No external Python dependencies

## Development

1. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Install dependencies: `uv sync`
3. Install pre-commit hooks: `uv tool install pre-commit && pre-commit install`
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
   - Start subject lines with an action verb in past tense (`Added`, `Changed`,
     `Fixed`, `Removed`).
   - Keep subjects user-facing so auto-generated release notes are meaningful.
   - Group related changes into focused commits instead of one broad commit.
   - Example: `Fixed timeout handling in status command`
5. Tag and push to all remotes (origin/GitHub, gitlab, codeberg):
   - `git tag vX.Y.Z`
   - `git push origin main && git push origin vX.Y.Z`
   - `git push gitlab main && git push gitlab vX.Y.Z`
   - `git push codeberg main && git push codeberg vX.Y.Z`
6. Confirm GitHub Actions:
   - CI should pass.
   - Publish workflow should upload to PyPI and create GitHub Release notes.
   - Release notes should include generated notes plus a commit summary from the
     previous tag to the current tag.

## License

Apache-2.0

## macOS quarantine during installation

After successful installs and upgrades, code-aide removes the
`com.apple.quarantine` attribute from the installed npm package (including
nested native helpers), direct-download directory, or verified app bundle.
Script installs clear their configured artifact paths and resolved command.
Homebrew upgrades clear the selected formula or cask directory. Symlinks inside
these directories are not followed into other installations.

This addresses Gatekeeper prompts that can block unattended use, including
Codex's `codex-code-mode-host` helper and the resulting "timed out negotiating
with the code-mode host" error when quarantine is the cause. Helpers do not need
to be on `PATH`. Other causes of that timeout are unaffected.

Cleanup preserves other extended attributes and does not change system-wide
Gatekeeper settings. It runs without `sudo`; permission failures are reported as
install or upgrade failures, leaving the installed files in place. Dry runs and
non-macOS hosts do not change extended attributes. Existing installs can be
processed with `code-aide install --force TOOL` or `code-aide upgrade TOOL`.
Updates performed independently by a tool's own updater are outside this step.

## npm download cache lifetime

Standalone install, upgrade, removal (including migration), and installation
scripts use private download caches under
`~/.cache/code-aide/npm-operations/operation-*`. Each invocation gets its own
directory on the home filesystem instead of the temporary filesystem. npm
authentication, user configuration and install prefixes remain in effect; only
the download-cache setting is overridden in the child environment.

Downloads and npm logs in that directory are removed after success, failure,
timeouts supported by the command runner, and normal Python interruption.
Captured command errors are still reported. Existing user caches are preserved.
Dry runs create no operation cache. Concurrent operations never clean another
operation's cache. A hard kill or machine crash can leave an operation
directory; inspect it and establish that its operation has stopped before
explicitly removing it. There is no automatic age-based cleanup of these
directories.

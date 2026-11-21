# TODO

Keep the project focused on managing AI coding CLI tools (install, upgrade,
remove, status, and version metadata).

All items below are deferred; none are scheduled.

| # | Item                           | Risk | Effort | Notes                                                  |
|:---|:-------------------------------|:-----|:-------|:-------------------------------------------------------|
| 1 | `doctor` command               | Low  | Med    | Health checks exist but are scattered                  |
| 2 | Cross-distro package detection | Med  | High   | Only Gentoo supported; other Linux distros get nothing |
| 3 | Split large modules            | Low  | High   | Refactoring only; no behavior change                   |
| 4 | Tests for edge cases           | Med  | Med    | PATH oddities, more version parsing corners            |
| 5 | Stop Antigravity profile edits | Low  | Med    | Installer appends PATH lines to shell profiles         |

## CLI and Automation UX

- [ ] Add a focused `doctor` command for environment checks (PATH,
  prerequisites, command health).

## Platform and Package Detection

- [ ] Broaden system package metadata detection beyond Gentoo-specific tooling
  where practical; note that non-Gentoo system installs currently report "up to
  date" because no available version is detectable.

## Installer Side Effects

- [ ] Figure out a way to stop the Antigravity CLI installer from editing shell
  profiles. Installing `agy` appended `# Added by Antigravity CLI installer` and
  `export PATH="$HOME/.local/bin:$PATH"` to `~/.bash_profile` and `~/.profile`.
  On hosts where those files are symlinks into a dotfiles repository, this
  dirties the repository and duplicates a PATH entry the dotfiles already set.
  - `install.sh` itself does not touch profiles; its last step runs `agy
    install` (or `agy install --dir DIR`) with no way to pass flags through.
  - `agy install` accepts `--skip-path` (no PATH appending) and `--skip-aliases`
    (no alias purging), so the fix is likely to get that call made with
    `--skip-path`: for example, replicate the script's download, checksum, and
    extract steps in code-aide and run `agy install --skip-path` ourselves, or
    ask upstream to honor a flag or environment variable in `install.sh`.
  - Check whether `agy` self-updates (`self_updates: true`) re-run the profile
    step, and whether `code-aide upgrade` hits the same path.

## Maintainability and Tests

- [ ] Split larger modules into smaller focused files where practical
  (`install.py`, `commands_actions.py`, `versions.py`).
- [ ] Add tests for more prerequisite edge cases and PATH oddities.

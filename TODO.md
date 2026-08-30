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

## CLI and Automation UX

- [ ] Add a focused `doctor` command for environment checks (PATH,
  prerequisites, command health).

## Platform and Package Detection

- [ ] Broaden system package metadata detection beyond Gentoo-specific tooling
  where practical; note that non-Gentoo system installs currently report "up to
  date" because no available version is detectable.

## Maintainability and Tests

- [ ] Split larger modules into smaller focused files where practical
  (`install.py`, `commands_actions.py`, `versions.py`).
- [ ] Add tests for more prerequisite edge cases and PATH oddities.

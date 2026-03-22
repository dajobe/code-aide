# Unify upgrade eligibility with a shared evaluator

## Summary

Introduce a single evaluator class that computes tool state once and exposes
normalized decisions for both `status` and default `upgrade`. Use typed
`Enum` values, not strings, for all decision outcomes and display states so
callers cannot drift by comparing ad hoc literals.

## Implementation changes

- Add a small evaluator in `src/code_aide/status.py` as the single source of
  truth for:
  - install presence
  - detected install method
  - package-manager metadata
  - version relationship to catalog/package state
  - normalized outcome for both status rendering and default `upgrade`
- Define typed enums for evaluator output:
  - `UpgradeDecision`: `CURRENT`, `UPGRADE`, `MIGRATION`, `PACKAGE_MANAGED`,
    `NOT_INSTALLED`, `UNKNOWN`
  - `VersionDisplayState`: `UP_TO_DATE`, `OUTDATED`, `UNAVAILABLE`
  - optional compact-state enum if needed, otherwise derive compact text
    from `UpgradeDecision`
- Return a typed result object/dataclass from the evaluator containing:
  - `decision: UpgradeDecision`
  - `version_state: VersionDisplayState`
  - `actionable_by_upgrade: bool`
  - optional package/upstream fields needed by full status
- Keep all decision rules inside the evaluator:
  - exact catalog match => `CURRENT`
  - installed newer than catalog => `CURRENT`
  - deprecated detected install (`npm`/`brew_npm` vs configured non-matching
    method) => `MIGRATION`
  - Homebrew outdated => `UPGRADE`
  - Homebrew current => `CURRENT`
  - system-managed install => `PACKAGE_MANAGED`, never auto-selected by
    default `upgrade`
  - missing latest-version metadata or missing CLI version => `UNKNOWN`, not
    auto-selected
- Refactor `cmd_status` and compact status in
  `src/code_aide/commands_tools.py` to consume evaluator results only.
- Refactor default-selection logic in `cmd_upgrade` in
  `src/code_aide/commands_actions.py` to use the same evaluator result.
- Keep explicit `code-aide upgrade <tool>` behavior unchanged; the evaluator
  governs automatic selection and status semantics.

## Public interfaces and types

- Add an internal evaluator class, for example `ToolUpgradeEvaluator`.
- Add internal enums and a typed result/dataclass; no caller should branch
  on raw strings after this refactor.
- Do not change CLI flags, command names, or user-facing command flow.

## Test plan

- Add evaluator-focused unit tests covering enum outputs for:
  - installed version equals catalog latest
  - installed version newer than catalog latest
  - installed version older than catalog latest
  - Homebrew tool with `outdated=True`
  - Homebrew tool with `outdated=False`
  - system-managed tool with newer upstream metadata
  - deprecated npm install requiring migration
  - missing version metadata or unknown state
- Add command-level regressions proving shared behavior:
  - full `status` says `up to date` for newer-than-catalog installs and
    default `upgrade` does not auto-select them
  - full/compact `status` and default `upgrade` both treat Homebrew current
    installs as non-upgradeable
  - system-managed installs are not auto-selected by default `upgrade`
  - migration-required installs still appear as actionable for default
    `upgrade`
- Run the targeted suite:
  - `tests/test_status.py`
  - `tests/test_commands_tools.py`
  - `tests/test_commands_actions.py`
  - any existing detection/operations tests touched by the refactor

## Assumptions

- The evaluator, enums, and result dataclass remain internal APIs.
- Full `status` still shows migration warnings separately from upgrade
  footers, but both are derived from the same enum-backed evaluator result.
- `Upgradeable` in the footer means `selected by default code-aide upgrade`.
- Display text remains string-based at the CLI boundary only; decision logic
  uses enums throughout.

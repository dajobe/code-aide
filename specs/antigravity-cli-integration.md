# Add Antigravity CLI support

## Context

Google transitioned consumer Gemini CLI access to Antigravity CLI on June 18,
2026. Gemini CLI remains valid for enterprise, Google Cloud, and supported API
key authentication, so code-aide must manage the two commands separately and
must not remove or migrate existing Gemini installations.

## Design

- Add Antigravity as the default tool key `antigravity`, using command `agy`.
- Install it through Google's native script and verify the archived script's
  SHA-256 before execution.
- Query the installer's official platform manifest and read its `version` field
  when refreshing the latest-version cache.
- Record that `agy` uses its native background self-updater, so code-aide does
  not repeatedly invoke an installer that intentionally exits when the binary
  already exists.
- Keep Gemini CLI available as an opt-in npm tool with updated authentication
  guidance.
- Do not infer a user's Google subscription or automatically migrate Gemini.

The manifest URL uses `{platform}` values such as `darwin_arm64` and
`linux_amd64`. The formatter supports the macOS and Linux architectures that the
upstream Unix installer supports.

## Verification

1. Confirm the archived installer exactly matches the configured SHA-256.
2. Test manifest URL formatting and JSON version extraction.
3. Run `uv run pytest` and `pre-commit run --all-files`.
4. Dry-run `code-aide update-versions` and confirm Antigravity reports the
   manifest version.

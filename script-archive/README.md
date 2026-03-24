# Script Archive

This directory contains archived copies of third-party install scripts used
by code-aide. These are committed so that when an upstream script changes
(detected by SHA256 mismatch during upgrade), you can diff the new version
against the known-good archived copy.

## When a SHA256 verification fails

1. Download the new script to a temp file:

       curl -fsSL <install_url> -o /tmp/new-script.sh

2. Diff against the archived version:

       diff script-archive/<tool>-install.sh /tmp/new-script.sh

3. Review the changes for anything suspicious.

4. If the script is safe, update both the archive and the hash:

       cp /tmp/new-script.sh script-archive/<tool>-install.sh
       # Update install_sha256 in src/code_aide/data/tools.json

5. Commit both changes together.

## Tool metadata

See `src/code_aide/data/tools.json` for install URLs, SHA256 hashes, and
per-tool notes (e.g. legacy script status).

## Pre-commit hooks

The `.pre-commit-config.yaml` excludes `script-archive/` from
`trailing-whitespace` and `end-of-file-fixer` hooks so that archived scripts
retain their exact upstream bytes.

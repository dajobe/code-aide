"""Keep mocked installer tests from inspecting or modifying real installations."""

import pytest

from code_aide import macos_quarantine


@pytest.fixture(autouse=True)
def isolate_quarantine_cleanup(request, monkeypatch):
    # These tests mock installers, sometimes using names of real local tools.
    # Quarantine behavior is exercised with isolated artifacts in its own tests.
    if request.module.__name__ in {
        "test_macos_quarantine",
        "test_quarantine_integration",
    }:
        return
    for name in (
        "clear_quarantine",
        "clear_npm_quarantine",
        "clear_script_quarantine",
        "clear_brew_quarantine",
    ):
        monkeypatch.setattr(macos_quarantine, name, lambda *args, **kwargs: True)

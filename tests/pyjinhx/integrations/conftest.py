from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _cwd_at_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chdir to tests/, so a bare ``request_scope()``'s default ``"templates"``
    resolves to tests/templates, matching how the FastAPI middleware runs
    without a caller-supplied template_dir.
    """
    monkeypatch.chdir(Path(__file__).parent.parent.parent)

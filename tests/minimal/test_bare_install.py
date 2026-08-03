"""What must hold when only the base distribution is installed.

Runnable against an environment with no fastapi/starlette, which is how CI's
minimal leg runs it; it must also pass in the full dev environment, so it
never asserts that the extra is absent.
"""

from __future__ import annotations

import importlib.util

import pytest


def test_importing_pyjinhx_needs_no_web_framework() -> None:
    import pyjinhx  # noqa: F401
    from pyjinhx.config import PjxSettings, setup  # noqa: F401


def test_setup_without_an_app_works() -> None:
    from pyjinhx.config import PjxSettings, setup

    resolved = setup(settings=PjxSettings(inject_htmx=False))
    assert resolved.inject_htmx is False


def test_setup_with_an_app_names_the_extra_when_it_is_missing() -> None:
    from pyjinhx.config import setup

    if importlib.util.find_spec("fastapi") is not None:
        pytest.skip("the fastapi extra is installed in this environment")
    with pytest.raises(ImportError, match=r"pyjinhx\[fastapi\]"):
        setup(app=object())

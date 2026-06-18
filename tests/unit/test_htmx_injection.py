import pytest

from pyjinhx.assets import (
    AssetMode,
    AssetPolicy,
    RenderSession,
    inject_runtime,
    set_inject_htmx,
)

pytestmark = pytest.mark.pjx_runtime  # let the real inject_runtime run


@pytest.fixture(autouse=True)
def _reset_inject_htmx():
    set_inject_htmx(True)
    yield
    set_inject_htmx(True)


def _inline_policy() -> AssetPolicy:
    return AssetPolicy(js_mode=AssetMode.INLINE, css_mode=AssetMode.INLINE)


def test_htmx_inlined_before_pjx_runtime_by_default():
    session = RenderSession()
    inject_runtime(session, policy=_inline_policy())

    blob = "\n".join(session.scripts)
    assert "var htmx" in blob, "vendored htmx should be inlined"
    assert "htmx:configRequest" in blob, "pjx.js runtime should be inlined"
    # htmx must come first so window.htmx exists before pjx.js registers listeners
    assert blob.index("var htmx") < blob.index("htmx:configRequest")


def test_htmx_guarded_against_double_load():
    session = RenderSession()
    inject_runtime(session, policy=_inline_policy())
    assert "if (!window.htmx)" in "\n".join(session.scripts)


def test_inject_htmx_disabled_skips_htmx_keeps_pjx():
    set_inject_htmx(False)
    session = RenderSession()
    inject_runtime(session, policy=_inline_policy())

    blob = "\n".join(session.scripts)
    assert "var htmx" not in blob, "htmx should be skipped when disabled"
    assert "htmx:configRequest" in blob, "pjx.js must still be injected"

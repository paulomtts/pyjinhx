"""PJXSelect multi-select mode (#866) — checkboxes, chip trigger summary, native multi.

Single-select behaviour lives in test_pjx_select.py. Search (#867), keyboard nav
(#868) and the exhaustive cross-cutting suite (#869) are separate subtasks;
nothing here anticipates their markup.
"""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_select import PJXSelect, SelectOption
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

OPTIONS = [
    SelectOption(value="a", label="Apple"),
    SelectOption(value="b", label="Banana"),
    SelectOption(value="c", label="Cherry"),
]


class TestMultipleFields:
    def test_multiple_defaults_to_false(self):
        assert PJXSelect(id="s", name="fruit", options=OPTIONS).multiple is False

    def test_multi_mode_accepts_a_list_value(self):
        sel = PJXSelect(
            id="s", name="fruit", options=OPTIONS, multiple=True, value=["a", "b"]
        )
        assert sel.value == ["a", "b"]

    def test_multi_mode_accepts_none(self):
        sel = PJXSelect(id="s", name="fruit", options=OPTIONS, multiple=True)
        assert sel.value is None

    def test_multiple_value_type_mismatch_raises(self):
        with pytest.raises(ValidationError):
            PJXSelect(id="s", name="fruit", options=OPTIONS, multiple=True, value="a")
        with pytest.raises(ValidationError):
            PJXSelect(id="s", name="fruit", options=OPTIONS, value=["a"])


@pytest.fixture
def session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    Same fixture shape as the sibling builtin tests.
    """
    return RenderSession()


def _html(session, **kwargs) -> str:
    base = {"id": "s", "name": "fruit", "options": OPTIONS}
    base.update(kwargs)
    return render(PJXSelect(**base), session)  # type: ignore[arg-type]


class TestMultipleMarkup:
    def test_multiple_renders_checkboxes(self, session):
        html = _html(session, multiple=True)
        assert html.count('type="checkbox"') == 3
        assert 'type="checkbox"' not in _html(session)

    def test_multiple_native_select_has_multiple_attr(self, session):
        assert '<select name="fruit" multiple hidden>' in _html(session, multiple=True)
        assert "multiple" not in _html(session)

    def test_multiple_root_carries_the_multiple_hook(self, session):
        head = _html(session, multiple=True)
        head = head[: head.index(">")]
        assert "data-multiple" in head
        assert 'data-placeholder="Select…"' in head

    def test_multiple_checked_state_follows_the_value_list(self, session):
        html = _html(session, multiple=True, value=["a", "c"])
        assert html.count("checkbox\" checked") == 2
        assert html.count('<option value="a" selected>') == 1
        assert html.count('<option value="c" selected>') == 1
        assert '<option value="b">' in html
        assert html.count('aria-selected="true"') == 2

    def test_multiple_unknown_value_dropped(self, session):
        html = _html(session, multiple=True, value=["a", "zzz"])
        assert html.count('aria-selected="true"') == 1
        assert html.count("checkbox\" checked") == 1
        assert "zzz" not in html

    def test_multiple_disabled_checkboxes_present_but_inert(self, session):
        html = _html(session, multiple=True, disabled=True)
        assert html.count('type="checkbox"') == 3
        assert html.count('type="checkbox" disabled') == 3
        assert "data-disabled" in html[: html.index(">")]

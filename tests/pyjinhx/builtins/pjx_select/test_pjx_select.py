"""PJXSelect — single-choice base: fields, markup, and no-JS form fallback.

Multi-select (#866), search (#867) and keyboard nav (#868) are separate
subtasks; nothing here anticipates their markup. The exhaustive suite is #869's.
"""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_select import PJXSelect, SelectOption
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

OPTIONS = [
    SelectOption(value="a", label="Apple"),
    SelectOption(value="b", label="Banana"),
]


class TestFields:
    def test_defaults(self):
        sel = PJXSelect(id="s", name="fruit", options=OPTIONS)
        assert sel.value is None
        assert sel.placeholder == "Select…"
        assert sel.disabled is False
        assert sel.class_name == ""

    def test_name_is_required(self):
        with pytest.raises(ValidationError):
            PJXSelect(id="s", options=OPTIONS)  # type: ignore[call-arg]

    def test_options_is_required(self):
        with pytest.raises(ValidationError):
            PJXSelect(id="s", name="fruit")  # type: ignore[call-arg]

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXSelect(id="s", name="fruit", options=OPTIONS, bogus="x")  # type: ignore[call-arg]

    def test_extra_attrs_defaults_empty(self):
        sel = PJXSelect(id="s", name="fruit", options=OPTIONS)
        assert sel.extra_attrs == {}

    def test_options_accept_plain_dicts(self):
        sel = PJXSelect(
            id="s",
            name="fruit",
            options=[{"value": "a", "label": "Apple"}],  # type: ignore[list-item]
        )
        assert sel.options[0].label == "Apple"

    def test_option_requires_both_value_and_label(self):
        with pytest.raises(ValidationError):
            SelectOption(value="a")  # type: ignore[call-arg]


def test_exported_from_the_builtins_namespace():
    from pyjinhx import builtins

    assert "PJXSelect" in builtins.__all__
    assert builtins.PJXSelect is PJXSelect


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


class TestRender:
    def test_single_root_div(self, session):
        html = _html(session).strip()
        assert html.count("data-pjx-select ") == 1
        assert html.startswith('<div id="s"')
        assert html.endswith("</div>")

    def test_extra_attrs_surface_on_the_root(self, session):
        html = _html(session, extra_attrs={"data-testid": "sel"})
        assert 'data-testid="sel"' in html

    def test_root_carries_the_name(self, session):
        head = _html(session, name="pick")
        assert 'data-name="pick"' in head[: head.index(">")]

    def test_hidden_native_select_posts_under_the_name(self, session):
        html = _html(session)
        assert '<select name="fruit"' in html
        assert html.count("<option ") == 2

    def test_hidden_select_marks_the_current_value_selected(self, session):
        html = _html(session, value="b")
        assert '<option value="b" selected>' in html
        assert '<option value="a">' in html

    def test_trigger_shows_the_placeholder_when_unselected(self, session):
        html = _html(session, placeholder="Pick a fruit")
        assert "Pick a fruit" in html
        assert "Apple" in html  # still listed as an option
        assert html.count("Pick a fruit") == 1

    def test_trigger_shows_the_selected_label(self, session):
        html = _html(session, value="b")
        trigger = html[html.index("data-pjx-select-trigger") :]
        assert "Banana" in trigger[: trigger.index("</button>")]

    def test_unknown_value_renders_unselected_without_raising(self, session):
        html = _html(session, value="zzz")
        # Every option carries aria-selected="false"/"true" by design (spec
        # step 17), so a bare "selected" not in html check is unsatisfiable —
        # "selected" is a substring of "aria-selected". Assert the precise
        # thing: no native <option> is marked selected, and no aria-selected
        # is "true".
        assert " selected>" not in html
        assert 'aria-selected="true"' not in html
        assert "Select…" in html

    def test_options_render_in_order_with_value_hooks(self, session):
        html = _html(session)
        assert html.count("data-pjx-select-option") == 2
        positions = [html.index(f'data-value="{v}"') for v in ("a", "b")]
        assert positions == sorted(positions)

    def test_selected_option_is_marked_for_keyboard_state(self, session):
        html = _html(session, value="a")
        assert 'data-value="a" aria-selected="true"' in html
        assert 'data-value="b" aria-selected="false"' in html

    def test_panel_is_hidden_until_opened(self, session):
        html = _html(session)
        assert 'class="pjx-select__panel" data-pjx-select-panel hidden' in html

    def test_disabled_flags_the_root_and_the_hidden_select(self, session):
        html = _html(session, disabled=True)
        assert "data-disabled" in html[: html.index(">")]
        assert '<select name="fruit" hidden disabled>' in html
        assert '<button type="button" class="pjx-select__trigger"' in html
        assert "disabled>" in html

    def test_not_disabled_by_default(self, session):
        html = _html(session)
        assert "data-disabled" not in html[: html.index(">")]
        assert "disabled" not in html

    def test_no_search_or_checkbox_markup(self, session):
        html = _html(session)
        assert 'type="search"' not in html
        assert 'type="checkbox"' not in html

    def test_class_name_is_appended_without_clobbering_base_classes(self, session):
        assert 'class="pjx-select my-select"' in _html(session, class_name="my-select")

    def test_empty_class_name_adds_nothing(self, session):
        assert 'class="pjx-select"' in _html(session)

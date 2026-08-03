"""PJXEmptyState renders a single-root empty state with suggestion chips (port of v0.x pyjinhx/builtins/ui/pjx_empty_state)."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_divider import PJXDivider
from pyjinhx.builtins.ui.pjx_empty_state import PJXEmptyState
from pyjinhx.render import render
from pyjinhx.session import RenderSession


@pytest.fixture
def empty_state_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    ClassDescriptor.template_path is absolute and render() feeds it straight to
    the session's FileSystemLoader; Jinja only resolves an absolute path when
    the loader root is "/". Same fixture shape as tests/pyjinhx/builtins/pjx_divider.
    """
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXEmptyState(id="e", **kw), session)


def test_default_render_is_single_empty_div(empty_state_session):
    html = _html(empty_state_session)
    assert html == '<div id="e" class="pjx-empty-state"></div>'


def test_no_suggestions_block_when_suggestions_is_empty(empty_state_session):
    html = _html(empty_state_session, content="Nothing here")
    assert "pjx-empty-state__suggestions" not in html
    assert "pjx-empty-state__chip" not in html


def test_string_content_renders_escaped_inside_root(empty_state_session):
    html = _html(empty_state_session, content="<script>x</script>")
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "<script>" not in html


def test_component_content_renders_nested(empty_state_session):
    html = _html(empty_state_session, content=PJXDivider(id="d"))
    assert html == (
        '<div id="e" class="pjx-empty-state">\n'
        '<hr id="d"\n'
        '    class="pjx-divider pjx-divider--horizontal"\n'
        '    role="separator"\n'
        '    aria-orientation="horizontal" />\n'
        "</div>"
    )


def test_class_name_appended_to_root(empty_state_session):
    html = _html(empty_state_session, class_name="mine")
    assert 'class="pjx-empty-state mine"' in html


def test_empty_class_name_adds_nothing(empty_state_session):
    html = _html(empty_state_session, class_name="")
    assert 'class="pjx-empty-state"' in html


def test_label_only_chip_defaults_value_and_event(empty_state_session):
    html = _html(empty_state_session, suggestions=[{"label": "Retry"}])
    assert html.count('class="pjx-empty-state__suggestions"') == 1
    assert html.count('class="pjx-empty-state__chip"') == 1
    assert 'data-pjx-suggestion="Retry"' in html
    assert 'data-pjx-event="pjx:suggestion"' in html
    assert ">Retry<" in html


def test_chip_value_and_event_override_the_defaults(empty_state_session):
    html = _html(
        empty_state_session,
        suggestions=[{"label": "Retry", "value": "retry-1", "event": "app:retry"}],
    )
    assert 'data-pjx-suggestion="retry-1"' in html
    assert 'data-pjx-event="app:retry"' in html
    assert 'data-pjx-suggestion="Retry"' not in html
    assert ">Retry<" in html


def test_multiple_chips_share_one_suggestions_wrapper(empty_state_session):
    html = _html(
        empty_state_session,
        suggestions=[{"label": "A"}, {"label": "B"}, {"label": "C"}],
    )
    assert html.count('class="pjx-empty-state__suggestions"') == 1
    assert html.count('class="pjx-empty-state__chip"') == 3
    assert ">A<" in html and ">B<" in html and ">C<" in html


def test_chip_label_renders_escaped(empty_state_session):
    html = _html(empty_state_session, suggestions=[{"label": "<script>x</script>"}])
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "<script>" not in html


def test_chip_click_dispatches_a_custom_event(empty_state_session):
    """Alpine's @click="$dispatch(...)" is gone (ADR 0012, no Alpine in v2).

    The observable contract kept is the chip emitting its data-pjx-event name
    with the suggestion value in detail.value; the mechanism is an inline
    listener, the smallest replacement that preserves it.
    """
    html = _html(empty_state_session, suggestions=[{"label": "Retry"}])
    assert "onclick=" in html
    assert "dispatchEvent" in html
    assert "@click" not in html


def test_undeclared_attr_is_rejected():
    """v2 core is strict (extra="forbid"): v0.x's extra_attrs pass-through is gone.

    Deliberate narrowing of v0.x behavior, matching the #500 precedent.
    """
    with pytest.raises(ValidationError):
        PJXEmptyState(id="e", extra_attrs={"data-x": "y"})  # pyright: ignore[reportCallIssue]

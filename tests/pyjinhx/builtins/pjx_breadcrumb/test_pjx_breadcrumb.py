"""PJXBreadcrumb renders the single-root <nav> trail of linked and current crumbs (port of v0.x pyjinhx/builtins/ui/pjx_breadcrumb)."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_breadcrumb import PJXBreadcrumb
from pyjinhx.render import render
from pyjinhx.session import RenderSession


@pytest.fixture
def breadcrumb_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXBreadcrumb(id="bc", **kw), session)


def test_default_render_is_empty_list_inside_nav(breadcrumb_session):
    """Missing items renders the shell with an empty <ol>: no error, no crumbs."""
    html = _html(breadcrumb_session)
    assert '<nav id="bc"' in html
    assert 'class="pjx-breadcrumb"' in html
    assert 'aria-label="Breadcrumb"' in html
    assert '<ol class="pjx-breadcrumb__list">' in html
    assert "<li" not in html
    assert "<a " not in html


def test_linked_item_renders_anchor(breadcrumb_session):
    html = _html(breadcrumb_session, items=[("Home", "/")])
    assert '<li class="pjx-breadcrumb__item">' in html
    assert '<a class="pjx-breadcrumb__link" href="/">Home</a>' in html
    assert "aria-current" not in html


def test_current_item_renders_span(breadcrumb_session):
    """A crumb with href=None is the current page: a span, never an anchor."""
    html = _html(breadcrumb_session, items=[("Settings", None)])
    assert (
        '<span class="pjx-breadcrumb__current" aria-current="page">Settings</span>'
        in html
    )
    assert "<a " not in html


def test_mixed_items_render_in_order(breadcrumb_session):
    html = _html(
        breadcrumb_session,
        items=[("Home", "/"), ("Reports", "/reports"), ("Q3", None)],
    )
    assert html.count("<li") == 3
    assert html.index("Home") < html.index("Reports") < html.index("Q3")
    assert 'href="/reports"' in html
    assert 'aria-current="page">Q3</span>' in html


def test_class_name_appended_to_root(breadcrumb_session):
    assert 'class="pjx-breadcrumb mine"' in _html(breadcrumb_session, class_name="mine")


def test_empty_class_name_adds_nothing(breadcrumb_session):
    assert 'class="pjx-breadcrumb"' in _html(breadcrumb_session, class_name="")


def test_aria_label_defaults_and_is_overridable(breadcrumb_session):
    assert PJXBreadcrumb.model_fields["aria_label"].default == "Breadcrumb"
    assert 'aria-label="You are here"' in _html(
        breadcrumb_session, aria_label="You are here"
    )


def test_clean_break_no_extra_attrs_field():
    """v2 core is strict (extra="forbid"): v0.x's extra_attrs pass-through is gone."""
    assert "extra_attrs" not in PJXBreadcrumb.model_fields


def test_undeclared_attr_is_rejected():
    with pytest.raises(ValidationError):
        PJXBreadcrumb(id="bc", extra_attrs={"data-x": "y"})  # pyright: ignore[reportCallIssue]


def test_json_string_items_still_coerced_by_core_hook():
    """The component-local _coerce_breadcrumb_items BeforeValidator is gone, but
    BaseComponent._coerce_json_string_attrs (generic, applies to every strict
    list-typed field) still parses a JSON-looking string before Pydantic sees
    it — so this is NOT a behavior change from v0.x, just a different hook."""
    bc = PJXBreadcrumb(id="bc", items='[["Home", "/"]]')  # pyright: ignore[reportArgumentType]
    assert bc.items == [("Home", "/")]

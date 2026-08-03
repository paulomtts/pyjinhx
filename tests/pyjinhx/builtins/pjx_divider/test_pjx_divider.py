"""PJXDivider renders a single-root separator (port of v0.x pyjinhx/builtins/ui/pjx_divider)."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_divider import PJXDivider
from pyjinhx.render import render
from pyjinhx.session import RenderSession


@pytest.fixture
def divider_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    ClassDescriptor.template_path is absolute and render() feeds it straight to
    the session's FileSystemLoader; Jinja only resolves an absolute path when
    the loader root is "/". Same fixture shape as tests/pyjinhx/builtins/pjx_badge.
    """
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXDivider(id="d", **kw), session)


def test_default_render_is_single_hr(divider_session):
    html = _html(divider_session)
    assert html.count("<hr") == 1
    assert html.count("<div") == 0
    assert 'id="d"' in html
    assert 'role="separator"' in html
    assert 'aria-orientation="horizontal"' in html
    assert "pjx-divider pjx-divider--horizontal" in html


def test_vertical_render_is_single_div(divider_session):
    html = _html(divider_session, orientation="vertical")
    assert html.count("<div") == 1
    assert html.count("<hr") == 0
    assert 'role="separator"' in html
    assert 'aria-orientation="vertical"' in html
    assert "pjx-divider pjx-divider--vertical" in html


def test_vertical_with_label_sets_aria_label(divider_session):
    html = _html(divider_session, orientation="vertical", label="Or")
    assert html.count("<div") == 1
    assert 'aria-label="Or"' in html


def test_labeled_render_is_single_div_with_two_lines_and_label(divider_session):
    html = _html(divider_session, label="Or")
    assert html.count("<hr") == 0
    assert html.count('class="pjx-divider pjx-divider--labeled"') == 1
    assert html.count('class="pjx-divider__line"') == 2
    assert html.count('class="pjx-divider__label"') == 1
    assert ">Or<" in html


def test_label_renders_escaped_text(divider_session):
    html = _html(divider_session, label="<script>x</script>")
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "<script>" not in html


def test_class_name_appended_on_horizontal(divider_session):
    html = _html(divider_session, class_name="mine")
    assert 'class="pjx-divider pjx-divider--horizontal mine"' in html


def test_class_name_appended_on_vertical(divider_session):
    html = _html(divider_session, orientation="vertical", class_name="mine")
    assert 'class="pjx-divider pjx-divider--vertical mine"' in html


def test_class_name_appended_on_labeled(divider_session):
    html = _html(divider_session, label="Or", class_name="mine")
    assert 'class="pjx-divider pjx-divider--labeled mine"' in html


def test_empty_class_name_adds_nothing(divider_session):
    html = _html(divider_session, class_name="")
    assert 'class="pjx-divider pjx-divider--horizontal"' in html


def test_invalid_orientation_is_rejected():
    with pytest.raises(ValidationError):
        PJXDivider(id="d", orientation="sideways")  # pyright: ignore[reportArgumentType]


def test_undeclared_attr_is_rejected():
    """v2 core is strict (extra="forbid"): v0.x's extra_attrs pass-through is gone.

    Deliberate narrowing of v0.x behavior, matching the #500 precedent.
    """
    with pytest.raises(ValidationError):
        PJXDivider(id="d", extra_attrs={"data-x": "y"})  # pyright: ignore[reportCallIssue]

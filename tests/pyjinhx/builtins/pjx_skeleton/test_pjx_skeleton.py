"""PJXSkeleton renders a single-root loading placeholder (port of v0.x pyjinhx/builtins/ui/pjx_skeleton)."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_skeleton import PJXSkeleton
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def skeleton_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    ClassDescriptor.template_path is absolute and render() feeds it straight to
    the session's FileSystemLoader; Jinja only resolves an absolute path when
    the loader root is "/". Same fixture shape as tests/pyjinhx/builtins/pjx_divider.
    """
    return RenderSession()


def _html(session, **kw) -> str:
    return render(PJXSkeleton(id="s", **kw), session)


def test_default_render_is_text_variant_with_three_lines(skeleton_session):
    html = _html(skeleton_session)
    assert html.count('class="pjx-skeleton pjx-skeleton--text"') == 1
    assert html.count('class="pjx-skeleton__line"') == 3
    assert 'id="s"' in html


def test_lines_controls_line_count(skeleton_session):
    html = _html(skeleton_session, lines=5)
    assert html.count('class="pjx-skeleton__line"') == 5


def test_circle_variant_renders_single_circle(skeleton_session):
    html = _html(skeleton_session, variant="circle")
    assert html.count('class="pjx-skeleton pjx-skeleton--circle"') == 1
    assert html.count('class="pjx-skeleton__circle"') == 1
    assert html.count('class="pjx-skeleton__line"') == 0
    assert html.count("<div") == 2


def test_rect_variant_renders_single_rect(skeleton_session):
    html = _html(skeleton_session, variant="rect")
    assert html.count('class="pjx-skeleton pjx-skeleton--rect"') == 1
    assert html.count('class="pjx-skeleton__rect"') == 1
    assert html.count('class="pjx-skeleton__line"') == 0
    assert html.count("<div") == 2


def test_lines_is_ignored_for_non_text_variants(skeleton_session):
    html = _html(skeleton_session, variant="circle", lines=7)
    assert html.count('class="pjx-skeleton__circle"') == 1
    assert html.count('class="pjx-skeleton__line"') == 0


def test_class_name_appended_to_root(skeleton_session):
    html = _html(skeleton_session, class_name="mine")
    assert 'class="pjx-skeleton pjx-skeleton--text mine"' in html


def test_empty_class_name_adds_nothing(skeleton_session):
    html = _html(skeleton_session, class_name="")
    assert 'class="pjx-skeleton pjx-skeleton--text"' in html


def test_invalid_variant_is_rejected():
    with pytest.raises(ValidationError):
        PJXSkeleton(id="s", variant="blob")  # pyright: ignore[reportArgumentType]


def test_undeclared_attr_is_rejected():
    """v2 core is strict (extra="forbid"): v0.x's extra_attrs pass-through is gone.

    Deliberate narrowing of v0.x behavior, matching the #500 precedent.
    """
    with pytest.raises(ValidationError):
        PJXSkeleton(id="s", extra_attrs={"data-x": "y"})  # pyright: ignore[reportCallIssue]

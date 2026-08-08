"""PJXBadge renders a single-root themeable label span (port of v0.x pyjinhx/builtins/ui/pjx_badge)."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_badge import PJXBadge
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def badge_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    ClassDescriptor.template_path is absolute and render() feeds it straight to
    the session's FileSystemLoader; Jinja only resolves an absolute path when
    the loader root is "/". Same fixture shape as tests/pyjinhx/builtins/pjx_icon.
    """
    return RenderSession()


def _html(session, **kw) -> str:
    return render(PJXBadge(id="b", **kw), session)


def test_default_render(badge_session):
    html = _html(badge_session)
    assert html.count("<span") == 1
    assert 'id="b"' in html
    assert 'class="pjx-badge pjx-badge--neutral pjx-badge--md"' in html
    assert html.endswith(
        '--md"></span>'
    )  # nothing rendered between the tag and </span>: label defaults to ""


@pytest.mark.parametrize("color", ["brand", "error", "neutral", "muted"])
def test_color_variants(badge_session, color):
    html = _html(badge_session, color=color)
    assert f"pjx-badge--{color}" in html


@pytest.mark.parametrize("shape", ["square", "sm", "md", "full"])
def test_shape_variants(badge_session, shape):
    html = _html(badge_session, shape=shape)
    assert f"pjx-badge--{shape}" in html


def test_class_name_appended_space_separated(badge_session):
    html = _html(badge_session, class_name="mine")
    assert 'class="pjx-badge pjx-badge--neutral pjx-badge--md mine"' in html


def test_empty_class_name_adds_nothing(badge_session):
    html = _html(badge_session, class_name="")
    assert 'class="pjx-badge pjx-badge--neutral pjx-badge--md"' in html


def test_label_renders_escaped_text(badge_session):
    html = _html(badge_session, label="<b>New</b>")
    assert "&lt;b&gt;New&lt;/b&gt;" in html
    assert "<b>New</b>" not in html


def test_invalid_literal_is_rejected():
    with pytest.raises(ValidationError):
        PJXBadge(id="b", color="chartreuse")  # pyright: ignore[reportArgumentType]


def test_undeclared_attr_is_rejected():
    """v2 core is strict (extra="forbid"): v0.x's extra_attrs pass-through is gone.

    Deliberate narrowing of v0.x behavior, matching the #500 precedent.
    """
    with pytest.raises(ValidationError):
        PJXBadge(id="b", **{"data-x": "y"})  # pyright: ignore[reportCallIssue, reportArgumentType]


def test_extra_attrs_surface_on_the_root(badge_session):
    html = _html(badge_session, extra_attrs={"data-testid": "b1"})
    assert 'data-testid="b1"' in html


def test_descriptor_finds_snake_case_css():
    """The descriptor probes "<snake_case class name>.css" next to the module.

    Mirrors tests/pyjinhx/builtins/pjx_avatar/test_pjx_avatar.py: css_paths is a
    tuple with 0 or 1 entries (one probe per class, per ADR 0007).
    """
    css_paths = PJXBadge.__pjx_descriptor__.css_paths
    assert len(css_paths) == 1
    assert css_paths[0].name == "pjx_badge.css"


@pytest.mark.parametrize("color", ["brand", "error", "neutral", "muted"])
def test_css_styles_every_color_variant(color):
    """Every value of the color Literal has a matching rule; none renders unstyled."""
    css = PJXBadge.__pjx_descriptor__.css_paths[0].read_text(encoding="utf-8")
    assert f".pjx-badge--{color}" in css


@pytest.mark.parametrize("shape", ["square", "sm", "md", "full"])
def test_css_styles_every_shape_variant(shape):
    css = PJXBadge.__pjx_descriptor__.css_paths[0].read_text(encoding="utf-8")
    assert f".pjx-badge--{shape}" in css


def test_css_uses_shared_tokens_not_hardcoded_hex():
    """Colors come from docs/demos/base.css tokens so light/dark repaint for free."""
    css = PJXBadge.__pjx_descriptor__.css_paths[0].read_text(encoding="utf-8")
    assert ":where(:root)" in css
    assert "--pjx-badge-" in css
    assert "var(--brand" in css
    assert "var(--error" in css
    assert "#" not in css

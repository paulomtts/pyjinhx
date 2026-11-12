"""PJXBadge renders a single-root themeable label span (port of v0.x pyjinhx/builtins/ui/pjx_badge)."""

import re

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


@pytest.mark.parametrize(
    "color", ["brand", "error", "neutral", "muted", "info", "success", "warning"]
)
def test_color_variants(badge_session, color):
    html = _html(badge_session, color=color)
    assert f"pjx-badge--{color}" in html


@pytest.mark.parametrize("color", ["info", "success", "warning"])
def test_status_color_renders_exact_markup(badge_session, color):
    assert _html(badge_session, color=color) == (
        f'<span id="b" class="pjx-badge pjx-badge--{color} pjx-badge--md"></span>'
    )


@pytest.mark.parametrize("color", ["info", "success", "warning"])
def test_status_color_composes_with_class_name_and_removable(badge_session, color):
    html = _html(badge_session, color=color, class_name="mine")
    assert f'class="pjx-badge pjx-badge--{color} pjx-badge--md mine"' in html
    html = _html(badge_session, color=color, removable=True)
    assert f"pjx-badge--{color}" in html
    assert "pjx-badge--removable" in html
    assert "data-pjx-badge-remove" in html


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


@pytest.mark.parametrize(
    "color", ["brand", "error", "neutral", "muted", "info", "success", "warning"]
)
def test_css_styles_every_color_variant(color):
    """Every value of the color Literal has a matching rule; none renders unstyled."""
    css = PJXBadge.__pjx_descriptor__.css_paths[0].read_text(encoding="utf-8")
    assert f".pjx-badge--{color}" in css


@pytest.mark.parametrize("shape", ["square", "sm", "md", "full"])
def test_css_styles_every_shape_variant(shape):
    css = PJXBadge.__pjx_descriptor__.css_paths[0].read_text(encoding="utf-8")
    assert f".pjx-badge--{shape}" in css


def _css() -> str:
    """The badge stylesheet with whitespace collapsed to single spaces."""
    css = PJXBadge.__pjx_descriptor__.css_paths[0].read_text(encoding="utf-8")
    return " ".join(css.split())


def _rule(selector: str) -> str:
    """The body of the first rule whose selector is exactly `selector`."""
    match = re.search(re.escape(selector) + r" \{([^}]*)\}", _css())
    assert match, f"no {selector} rule"
    return match.group(1)


def test_css_uses_theme_tokens():
    """Defaults live in :where(:root) so app overrides win, and read theme tokens."""
    css = _css()
    assert ":where(:root)" in css
    assert "--pjx-badge-" in css
    assert "var(--pjx-color-brand" in css
    assert "var(--pjx-color-error" in css


def test_error_variant_uses_the_full_error_set():
    """The label reads error-text, the token designed to sit on error-subtle."""
    css = _css()
    assert "--pjx-badge-error-bg: var(--pjx-color-error-subtle, #fef2f2);" in css
    assert "--pjx-badge-error-text: var(--pjx-color-error-text, #991b1b);" in css
    assert "--pjx-badge-error-border: var(--pjx-color-error-border, #fecaca);" in css


STATUS_SETS = [
    ("info", "#f0f9ff", "#075985", "#bae6fd"),
    ("success", "#f0fdf4", "#166534", "#bbf7d0"),
    ("warning", "#fffbeb", "#92400e", "#fde68a"),
]


@pytest.mark.parametrize(("status", "subtle", "text", "border"), STATUS_SETS)
def test_status_variants_use_their_full_status_set(status, subtle, text, border):
    """Each status badge reads its own subtle/text/border trio with the light fallback."""
    css = _css()
    assert (
        f"--pjx-badge-{status}-bg: var(--pjx-color-{status}-subtle, {subtle});" in css
    )
    assert f"--pjx-badge-{status}-text: var(--pjx-color-{status}-text, {text});" in css
    assert (
        f"--pjx-badge-{status}-border: var(--pjx-color-{status}-border, {border});"
        in css
    )


@pytest.mark.parametrize("status", ["info", "success", "warning"])
def test_status_tokens_live_in_the_overridable_root_block(status):
    """Zero-specificity :where(:root) lets an app's :root override win."""
    root = _rule(":where(:root)")
    for part in ("bg", "text", "border"):
        assert f"--pjx-badge-{status}-{part}:" in root


@pytest.mark.parametrize("status", ["info", "success", "warning"])
def test_status_rule_reads_its_own_tokens(status):
    body = _rule(f".pjx-badge--{status}")
    assert f"background: var(--pjx-badge-{status}-bg);" in body
    assert f"color: var(--pjx-badge-{status}-text);" in body
    assert f"border-color: var(--pjx-badge-{status}-border);" in body


def test_spacing_follows_the_spacing_scale():
    css = _css()
    assert "--pjx-badge-padding: 0.2rem var(--pjx-space-2, 0.5rem);" in css
    assert "padding: var(--pjx-space-1, 0.25rem) 0.6rem;" in _rule(".pjx-badge--md")
    assert "padding: var(--pjx-space-1, 0.25rem) var(--pjx-space-3, 0.75rem);" in _rule(
        ".pjx-badge--full"
    )


def test_size_corners_follow_the_radius_scale():
    assert "border-radius: var(--pjx-radius-md, 8px);" in _rule(".pjx-badge--md")
    assert "border-radius: var(--pjx-radius-full, 9999px);" in _rule(".pjx-badge--full")


@pytest.mark.parametrize(
    "selector",
    [
        ".pjx-badge",
        ".pjx-badge--brand",
        ".pjx-badge--error",
        ".pjx-badge--info",
        ".pjx-badge--success",
        ".pjx-badge--warning",
        ".pjx-badge--neutral",
        ".pjx-badge--muted",
    ],
)
def test_rule_bodies_read_component_tokens_without_fallbacks(selector):
    """:where(:root) always declares the badge tokens, so a second fallback only duplicates it."""
    assert not re.search(r"var\(--pjx-badge-[\w-]+,", _rule(selector))


def test_removable_renders_the_remove_button(badge_session):
    html = _html(badge_session, removable=True)
    assert "pjx-badge--removable" in html
    assert "data-pjx-badge-remove" in html
    assert 'aria-label="Remove"' in html


def test_remove_label_overrides_the_button_aria_label(badge_session):
    html = _html(badge_session, removable=True, remove_label="Dismiss tag")
    assert 'aria-label="Dismiss tag"' in html


def test_non_removable_omits_the_remove_button(badge_session):
    html = _html(badge_session)
    assert "pjx-badge--removable" not in html
    assert "data-pjx-badge-remove" not in html


def test_remove_attrs_surface_on_the_remove_button(badge_session):
    html = _html(
        badge_session, removable=True, remove_attrs={"hx-post": "/tags/1/remove"}
    )
    assert 'hx-post="/tags/1/remove"' in html


def test_default_render_is_byte_identical_to_before(badge_session):
    """Adding the removable affordance must not change the non-removable render."""
    assert _html(badge_session, label="Active", color="brand") == (
        '<span id="b" class="pjx-badge pjx-badge--brand pjx-badge--md">Active</span>'
    )

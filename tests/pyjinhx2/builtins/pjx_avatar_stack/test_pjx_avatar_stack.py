"""PJXAvatarStack renders overlapping avatar pills (port of v0.x pyjinhx/builtins/ui/pjx_avatar_stack)."""

import pytest
from pydantic import ValidationError

from pyjinhx2.builtins.ui.pjx_avatar_stack import PJXAvatarStack
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession


@pytest.fixture
def stack_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    Same fixture shape as tests/pyjinhx2/builtins/pjx_badge.
    """
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXAvatarStack(id="s", **kw), session)


def test_empty_stack_with_empty_label_shows_empty_state(stack_session):
    html = _html(stack_session, empty_label="No one yet")
    assert '<span class="pjx-avatar-stack__empty">No one yet</span>' in html


def test_empty_stack_without_empty_label_shows_nothing(stack_session):
    html = _html(stack_session)
    assert "pjx-avatar-stack__empty" not in html
    assert "pjx-avatar-stack__pill" not in html


def test_empty_label_is_suppressed_once_there_are_avatars(stack_session):
    html = _html(stack_session, avatars=[{"initials": "AL"}], empty_label="No one yet")
    assert "pjx-avatar-stack__empty" not in html


def test_mapping_avatar_renders_a_pill(stack_session):
    html = _html(stack_session, avatars=[{"initials": "AL", "color": "#f00"}])
    assert '<span class="pjx-avatar pjx-avatar-stack__pill"' in html
    assert 'style="background:#f00;"' in html
    assert ">AL<" in html


def test_mapping_avatar_without_initials_falls_back_to_question_mark(stack_session):
    html = _html(stack_session, avatars=[{}])
    assert ">?<" in html


def test_mapping_avatar_initials_are_sliced_to_two_in_the_template(stack_session):
    html = _html(stack_session, avatars=[{"initials": "ABCD"}])
    assert ">AB<" in html
    assert "ABCD" not in html


def test_alt_becomes_tooltip_and_aria_label(stack_session):
    html = _html(stack_session, avatars=[{"initials": "AL", "alt": "Ada"}])
    assert 'title="Ada"' in html
    assert 'aria-label="Ada"' in html


def test_name_is_the_tooltip_fallback(stack_session):
    html = _html(stack_session, avatars=[{"initials": "AL", "name": "Ada"}])
    assert 'title="Ada"' in html


def test_alt_takes_precedence_over_name(stack_session):
    html = _html(
        stack_session, avatars=[{"initials": "AL", "alt": "Ada", "name": "Grace"}]
    )
    assert 'title="Ada"' in html
    assert "Grace" not in html


def test_no_tooltip_when_neither_alt_nor_name(stack_session):
    html = _html(stack_session, avatars=[{"initials": "AL"}])
    assert "title=" not in html
    assert "aria-label=" not in html


def test_plain_string_avatar_is_escaped(stack_session):
    """Invariant 6 regression guard: autoescape is on, so an HTML *string* is
    escaped. Raw markup must come in as a BaseComponent instead."""
    html = _html(stack_session, avatars=["<b>raw</b>"])
    assert "&lt;b&gt;raw&lt;/b&gt;" in html
    assert "<b>raw</b>" not in html


def test_extra_count_renders_overflow_badge(stack_session):
    html = _html(stack_session, extra_count=3)
    assert '<span class="pjx-avatar-stack__more" aria-label="3 more">+3</span>' in html


def test_zero_extra_count_omits_overflow_badge(stack_session):
    html = _html(stack_session, extra_count=0)
    assert "pjx-avatar-stack__more" not in html


def test_class_name_appended_space_separated(stack_session):
    html = _html(stack_session, class_name="mine")
    assert 'class="pjx-avatar-stack mine"' in html


def test_empty_class_name_adds_nothing(stack_session):
    html = _html(stack_session, class_name="")
    assert 'class="pjx-avatar-stack"' in html


def test_undeclared_attr_is_rejected():
    """v2 core is strict (extra="forbid"): v0.x's extra_attrs pass-through is gone."""
    with pytest.raises(ValidationError):
        PJXAvatarStack(id="s", **{"data-x": "y"})  # pyright: ignore[reportCallIssue, reportArgumentType]


def test_stylesheet_is_auto_discovered_by_snake_case_filename():
    css_paths = PJXAvatarStack.__pjx_descriptor__.css_paths
    assert len(css_paths) == 1
    assert css_paths[0].name == "pjx_avatar_stack.css"
    assert ".pjx-avatar-stack__pill" in css_paths[0].read_text(encoding="utf-8")


def test_base_component_avatar_renders_raw(stack_session):
    """A component in the list is the sanctioned way to get raw markup in.

    build_context() starts from model_dump(), which would flatten a component
    into a plain dict and send it down the "is mapping" pill branch, so
    `avatars` is marked as a slot field — that is what makes build_context
    re-read the live value and hand the template a ComponentNode.
    """
    from pyjinhx2.builtins.ui.pjx_avatar import PJXAvatar

    html = _html(stack_session, avatars=[PJXAvatar(id="inner", initials="AL")])
    assert 'id="inner"' in html
    assert 'class="pjx-avatar pjx-avatar--md"' in html
    assert "pjx-avatar-stack__pill" not in html
    assert "&lt;div" not in html

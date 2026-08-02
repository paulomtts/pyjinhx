"""PJXAvatar renders an image-or-initials circle (port of v0.x pyjinhx/builtins/ui/pjx_avatar)."""

import pytest
from pydantic import ValidationError

from pyjinhx2.builtins.ui.pjx_avatar import PJXAvatar
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession


@pytest.fixture
def avatar_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    ClassDescriptor.template_path is absolute and render() feeds it straight to
    the session's FileSystemLoader; Jinja only resolves an absolute path when
    the loader root is "/". Same fixture shape as tests/pyjinhx2/builtins/pjx_badge.
    """
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXAvatar(id="a", **kw), session)


def test_default_render_is_a_single_div_with_initials_fallback(avatar_session):
    html = _html(avatar_session)
    assert html.count("<div") == 1
    assert 'id="a"' in html
    assert 'class="pjx-avatar pjx-avatar--md"' in html
    assert ">?<" in html
    assert "<img" not in html


def test_src_renders_img_and_no_initials(avatar_session):
    html = _html(avatar_session, src="/u/1.png", alt="Ada")
    assert '<img class="pjx-avatar__img"' in html
    assert 'src="/u/1.png"' in html
    assert 'alt="Ada"' in html
    assert 'loading="lazy"' in html
    assert 'decoding="async"' in html
    assert "pjx-avatar__initials" not in html


def test_initials_render_when_no_src(avatar_session):
    html = _html(avatar_session, initials="AL")
    assert '<span class="pjx-avatar__initials"' in html
    assert ">AL<" in html


def test_initials_longer_than_two_chars_are_capped(avatar_session):
    assert PJXAvatar(id="a", initials="Ada Lovelace").initials == "Ad"
    html = _html(avatar_session, initials="Ada Lovelace")
    assert ">Ad<" in html


def test_initials_are_stripped_before_capping():
    assert PJXAvatar(id="a", initials="  AL  ").initials == "AL"


def test_empty_initials_stay_empty():
    assert PJXAvatar(id="a", initials="").initials == ""


@pytest.mark.parametrize("size", ["sm", "md", "lg"])
def test_token_sizes_emit_modifier_class_and_no_inline_size(avatar_session, size):
    html = _html(avatar_session, size=size)
    assert f"pjx-avatar--{size}" in html
    assert "width:" not in html


def test_int_size_omits_modifier_and_emits_inline_pixels(avatar_session):
    html = _html(avatar_session, size=36)
    assert "pjx-avatar--" not in html
    assert 'style="width:36px;height:36px;"' in html


def test_css_length_size_omits_modifier_and_emits_inline_length(avatar_session):
    html = _html(avatar_session, size="2.5rem")
    assert "pjx-avatar--" not in html
    assert 'style="width:2.5rem;height:2.5rem;"' in html


def test_color_adds_background_on_token_size(avatar_session):
    html = _html(avatar_session, color="#f00")
    assert "pjx-avatar--md" in html
    assert 'style="background:#f00;"' in html


def test_color_adds_background_on_non_token_size(avatar_session):
    html = _html(avatar_session, size=36, color="#f00")
    assert 'style="width:36px;height:36px;background:#f00;"' in html


def test_class_name_appended_space_separated(avatar_session):
    html = _html(avatar_session, class_name="mine")
    assert 'class="pjx-avatar pjx-avatar--md mine"' in html


def test_empty_class_name_adds_nothing(avatar_session):
    html = _html(avatar_session, class_name="")
    assert 'class="pjx-avatar pjx-avatar--md"' in html


def test_alt_adds_title_on_initials_span(avatar_session):
    html = _html(avatar_session, alt="Ada", initials="AL")
    assert 'title="Ada"' in html


def test_no_alt_omits_title_on_initials_span(avatar_session):
    html = _html(avatar_session, initials="AL")
    assert "title=" not in html


def test_undeclared_attr_is_rejected():
    """v2 core is strict (extra="forbid"): v0.x's extra_attrs pass-through is gone.

    Deliberate narrowing of v0.x behavior, matching the #500/#501 precedent.
    """
    with pytest.raises(ValidationError):
        PJXAvatar(id="a", **{"data-x": "y"})  # pyright: ignore[reportCallIssue, reportArgumentType]

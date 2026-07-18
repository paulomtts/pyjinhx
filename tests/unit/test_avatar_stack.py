from pyjinhx.builtins import PJXAvatar, PJXAvatarStack


def test_stack_renders_avatars_and_overflow():
    html = str(PJXAvatarStack(
        id="st",
        avatars=[PJXAvatar(id="a1", initials="AB"), PJXAvatar(id="a2", initials="CD")],
        extra_count=3,
    ).render())
    assert 'id="a1"' in html and 'id="a2"' in html
    assert ">+3<" in html
    assert 'aria-label="3 more"' in html
    assert html.index('id="a1"') < html.index('id="a2"')


def test_stack_empty_label():
    html = str(PJXAvatarStack(id="st", empty_label="Sem membros").render())
    assert "Sem membros" in html


def test_stack_no_empty_label_when_avatars_present():
    html = str(PJXAvatarStack(id="st", avatars=[PJXAvatar(id="a1", initials="AB")],
                           empty_label="Sem membros").render())
    assert "Sem membros" not in html


# --- Avatar arbitrary pixel size (issue #77) ---

def test_avatar_named_token_emits_bem_class():
    for token in ("sm", "md", "lg"):
        html = str(PJXAvatar(id="a", initials="AB", size=token).render())
        assert f"pjx-avatar--{token}" in html
        assert "style=" not in html


def test_avatar_int_size_emits_inline_style_no_bem():
    html = str(PJXAvatar(id="a", initials="AB", size=36).render())
    assert "width:36px" in html
    assert "height:36px" in html
    # BEM modifier must not appear on the root element; it may appear in the
    # embedded <style> block, so check the div tag specifically.
    assert 'class="pjx-avatar"' in html or 'class="pjx-avatar ' in html
    assert 'class="pjx-avatar pjx-avatar--' not in html


def test_avatar_css_length_string_emits_inline_style():
    html = str(PJXAvatar(id="a", initials="AB", size="2.5rem").render())
    assert "width:2.5rem" in html
    assert "height:2.5rem" in html
    assert 'class="pjx-avatar pjx-avatar--' not in html


def test_avatar_int_size_with_color():
    html = str(PJXAvatar(id="a", initials="AB", size=40, color="#ff0").render())
    assert "width:40px" in html
    assert "background:#ff0" in html


# --- AvatarStack structured dict data (issue #77) ---

def test_stack_dict_avatars_renders_pills():
    html = str(PJXAvatarStack(
        id="st",
        avatars=[
            {"initials": "AB", "color": "#f00", "name": "Alice"},
            {"initials": "CD"},
        ],
    ).render())
    assert "AB" in html
    assert "CD" in html
    assert 'style="background:#f00;"' in html
    assert 'title="Alice"' in html
    assert 'aria-label="Alice"' in html
    assert 'class="pjx-avatar pjx-avatar-stack__pill"' in html


def test_stack_dict_avatar_alt_takes_precedence_over_name():
    html = str(PJXAvatarStack(
        id="st",
        avatars=[{"initials": "XY", "color": "", "alt": "Explicit", "name": "Fallback"}],
    ).render())
    assert 'title="Explicit"' in html
    assert 'aria-label="Explicit"' in html
    assert "Fallback" not in html


def test_stack_mixed_dict_and_component():
    html = str(PJXAvatarStack(
        id="st",
        avatars=[
            {"initials": "DT", "color": "#0f0"},
            PJXAvatar(id="a1", initials="EF"),
        ],
        extra_count=1,
    ).render())
    assert "DT" in html
    assert 'id="a1"' in html
    assert ">+1<" in html


# --- Autoescape safety (issue #113) ---

def test_stack_dict_malicious_initials_are_escaped():
    """Dict field values (initials) are HTML-escaped; no XSS via pill text.
    The template slices initials to [:2], so only the first two chars render —
    but they must be escaped, not raw."""
    html = str(PJXAvatarStack(
        id="st",
        avatars=[{"initials": "<script>alert(1)</script>", "color": "red"}],
    ).render())
    assert "<script>" not in html
    assert "&lt;" in html   # the < is escaped (rendered as &lt;s after [:2] slice)


def test_stack_string_item_is_escaped():
    """Plain HTML strings passed as avatar items are escaped (autoescape is on)."""
    html = str(PJXAvatarStack(
        id="st",
        avatars=["<span class='x'>AB</span>"],
    ).render())
    assert "<span class='x'>AB</span>" not in html
    assert "&lt;span" in html

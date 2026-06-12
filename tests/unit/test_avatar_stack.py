from pyjinhx.builtins import PJXAvatar, PJXAvatarStack


def test_stack_renders_avatars_and_overflow():
    html = str(PJXAvatarStack(
        id="st",
        avatars=[PJXAvatar(id="a1", initials="AB"), PJXAvatar(id="a2", initials="CD")],
        extra_count=3,
    ).render())
    assert 'id="a1"' in html and 'id="a2"' in html
    assert ">+3<" in html
    assert html.index('id="a1"') < html.index('id="a2"')


def test_stack_empty_label():
    html = str(PJXAvatarStack(id="st", empty_label="Sem membros").render())
    assert "Sem membros" in html


def test_stack_no_empty_label_when_avatars_present():
    html = str(PJXAvatarStack(id="st", avatars=[PJXAvatar(id="a1", initials="AB")],
                           empty_label="Sem membros").render())
    assert "Sem membros" not in html

import pytest

from pyjinhx import Renderer


@pytest.fixture()
def env(tmp_path):
    (tmp_path / "card_hdr.html").write_text(
        '{#def title: str, count: int = 0 #}\n'
        '<div class="card">{{ title }}-{{ count }}</div>',
        encoding="utf-8",
    )
    (tmp_path / "plain_hdr.html").write_text("<div>{{ foo }}</div>", encoding="utf-8")
    Renderer.set_default_environment(str(tmp_path))
    return Renderer.get_default_renderer()


def test_header_applies_defaults(env):
    out = env.render('<CardHdr title="Hi"/>')
    assert "Hi-0" in out


def test_header_coerces_declared_prop(env):
    out = env.render('<CardHdr title="x" count="5"/>')
    assert "x-5" in out


def test_header_required_missing_errors(env):
    with pytest.raises(Exception) as exc:  # pydantic ValidationError surfaces
        env.render("<CardHdr/>")
    assert "title" in str(exc.value)


def test_undeclared_attr_passes_through_to_root(env):
    out = env.render('<CardHdr title="x" data-y="z"/>')
    assert 'data-y="z"' in out


def test_template_without_header_still_renders(env):
    out = env.render('<PlainHdr foo="bar"/>')
    assert "bar" in out

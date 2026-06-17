import os

import pytest

from pyjinhx import BaseComponent, component
from pyjinhx.renderer import Renderer


@pytest.fixture
def default_env(tmp_path):
    """Set a tmp_path default environment and restore the previous one after."""
    original = Renderer.peek_default_environment()
    Renderer.set_default_environment(tmp_path)
    try:
        yield tmp_path
    finally:
        Renderer.set_default_environment(original)


def _write(dir_path, filename, content):
    path = os.path.join(dir_path, filename)
    with open(path, "w") as file:
        file.write(content)
    return path


def test_component_renders_html_only_template(default_env):
    _write(default_env, "cf_card.html", '<div class="card"><h1>{{ title }}</h1>{{ content }}</div>')

    CfCard = component("CfCard")
    rendered = str(CfCard(title="Hi", content="body").render())

    assert '<div class="card">' in rendered
    assert "<h1>Hi</h1>" in rendered
    assert "body" in rendered


def test_component_nests_in_another_component(default_env):
    _write(default_env, "cf_widget.html", '<span class="widget">{{ content }}</span>')
    _write(
        default_env,
        "cf_host.html",
        '<section id="{{ id }}">{{ content }}<CfWidget>inner</CfWidget></section>',
    )

    CfWidget = component("CfWidget")
    CfHost = component("CfHost")

    host = CfHost(content="head")
    rendered = str(host.render())

    assert '<span class="widget">inner</span>' in rendered
    assert "head" in rendered
    assert "<section" in rendered


def test_tag_still_renders_after_factory(default_env):
    _write(default_env, "cf_badge.html", '<b id="{{ id }}">{{ content }}</b>')

    component("CfBadge")

    renderer = Renderer.get_default_renderer()
    rendered = renderer.render('<CfBadge id="b-1">tag</CfBadge>')
    assert rendered == '<b id="b-1">tag</b>'


def test_component_is_idempotent(default_env):
    first = component("CfIdem")
    second = component("CfIdem")
    assert first is second


def test_component_does_not_shadow_declared_class(default_env):
    class CfDeclared(BaseComponent):
        title: str = ""

    resolved = component("CfDeclared")
    assert resolved is CfDeclared


@pytest.mark.parametrize("bad_name", ["cf_card", "my-card", "card", "lowercase"])
def test_non_pascal_case_raises(bad_name):
    with pytest.raises(ValueError):
        component(bad_name)


def test_missing_template_raises_file_not_found(default_env):
    CfMissing = component("CfMissing")
    with pytest.raises(FileNotFoundError):
        CfMissing(content="x").render()

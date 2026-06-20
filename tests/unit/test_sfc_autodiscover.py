import textwrap

import pytest

from pyjinhx import Renderer
from pyjinhx.importer import install
from pyjinhx.registry import Registry
from pyjinhx.tags import ComponentAutodiscover


@pytest.fixture
def pjx_env(tmp_path, monkeypatch):
    install()
    monkeypatch.syspath_prepend(str(tmp_path))
    (tmp_path / "__init__.py").write_text("")
    Renderer.set_default_environment(str(tmp_path))
    yield tmp_path
    ComponentAutodiscover.clear()


def test_tag_resolves_to_pjx_class(pjx_env):
    (pjx_env / "badge.pjx").write_text(textwrap.dedent("""
        {# python
        from pyjinhx import BaseComponent

        class Badge(BaseComponent):
            count: int = 0
        #}
        <span class="badge">{{ count }}</span>
    """))
    # Render with explicit count=5 to check template works
    html = Renderer.get_default_renderer().render('<Badge count="5"/>')
    assert "badge" in html
    assert "5" in html
    # The Badge class must have been registered with its own defaults
    assert Registry.has_class("Badge"), "Badge class should be registered via .pjx autodiscovery"
    badge_cls = Registry.get_class("Badge")
    assert badge_cls.model_fields["count"].default == 0, "Badge.count default should be 0 (class registered)"


def test_broken_pjx_falls_through_to_colocated_fallback(pjx_env):
    """A .pjx with a {# python #} block that raises on exec must NOT halt
    autodiscovery — the co-located __init__.py defining the same class must
    still be picked up (regression for import_pjx_for_tag returning True on
    exec failure)."""
    comp_dir = pjx_env / "broken_widget_pkg"
    comp_dir.mkdir()

    # .pjx with a python block that raises at exec time
    (comp_dir / "broken_widget.pjx").write_text(
        "{# python\nraise RuntimeError('boom')\n#}\n<div>{{ label }}</div>"
    )
    # co-located __init__.py defines+registers the component
    (comp_dir / "__init__.py").write_text(textwrap.dedent("""
        from pyjinhx import BaseComponent

        class BrokenWidget(BaseComponent):
            label: str = "fallback-label"
    """))

    # Render — broken SFC logs a warning but must NOT block __init__.py fallback
    html = Renderer.get_default_renderer().render('<BrokenWidget/>')
    assert "fallback-label" in html
    assert Registry.has_class("BrokenWidget"), (
        "BrokenWidget must be registered from __init__.py; "
        "a broken .pjx (exec raises) must not block the co-located fallback"
    )
    widget_cls = Registry.get_class("BrokenWidget")
    assert widget_cls.model_fields["label"].default == "fallback-label"


def test_plain_pjx_falls_through_to_init_py_class(pjx_env):
    """A plain .pjx (no {# python #} block) must NOT block autodiscovery of an
    __init__.py that defines+registers the component class (regression for the
    unconditional `return` after the .pjx probe)."""
    # Put PlainWidget in a dedicated sub-directory so it has its own __init__.py
    # that is NOT the package root (which pjx_env already owns).
    comp_dir = pjx_env / "plain_widget_pkg"
    comp_dir.mkdir()

    # Plain .pjx — template only, no {# python #} block
    (comp_dir / "plain_widget.pjx").write_text(
        '<div class="plain-widget">{{ label }}</div>'
    )
    # __init__.py in the same directory registers PlainWidget
    (comp_dir / "__init__.py").write_text(textwrap.dedent("""
        from pyjinhx import BaseComponent

        class PlainWidget(BaseComponent):
            label: str = "default-label"
    """))

    # Render — autodiscovery must fall through the plain .pjx and pick up __init__.py
    html = Renderer.get_default_renderer().render('<PlainWidget/>')
    assert "plain-widget" in html
    assert "default-label" in html
    assert Registry.has_class("PlainWidget"), (
        "PlainWidget must be registered from __init__.py; "
        "a plain .pjx (no python block) must not block the __init__.py fallback"
    )
    widget_cls = Registry.get_class("PlainWidget")
    assert widget_cls.model_fields["label"].default == "default-label"

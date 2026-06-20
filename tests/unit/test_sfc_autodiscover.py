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

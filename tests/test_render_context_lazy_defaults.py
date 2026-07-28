"""Registry defaults must resolve lazily, not be copied per render (#240).

Peers used to be merged into every node's render context by id, which was
O(registered instances) per node. They are now resolved by name at the Jinja
layer (``renderer._PjxContext``), so the render context stays small -- but the
peer contract itself (``{{ peer }}`` / ``{{ peer.html }}`` /
``{{ peer.props.field }}``, deferred until referenced) must be unchanged.
"""

import importlib.util
import sys

from pyjinhx import Renderer
from pyjinhx.assets import RenderSession
from pyjinhx.registry import Registry
import pyjinhx.renderer as renderer_module


def _load_module(tmp_path, name: str, source: str):
    """Write and import a component module so template lookup (which is
    relative to the class's defining file) resolves inside ``tmp_path``."""
    module_path = tmp_path / f"{name}.py"
    module_path.write_text(source)
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_cross_reference_still_resolves(tmp_path):
    """A peer referenced by id from another component's template renders its
    real content through all three access forms."""

    (tmp_path / "lazy_host.html").write_text(
        '<section class="host-marker">'
        "[{{ lazy_peer }}][{{ lazy_peer.html }}][{{ lazy_peer.props.label }}]"
        "</section>"
    )
    (tmp_path / "lazy_peer.html").write_text('<span class="peer-marker">{{ label }}</span>')
    module = _load_module(
        tmp_path,
        "lazy_defaults_components",
        "from pyjinhx import BaseComponent\n\n"
        "class LazyHost(BaseComponent):\n"
        "    pass\n\n"
        "class LazyPeer(BaseComponent):\n"
        "    label: str = ''\n",
    )

    Renderer.set_default_environment(str(tmp_path))

    with Registry.request_scope():
        module.LazyPeer(id="lazy_peer", label="hello")
        host = module.LazyHost(id="lazy_host")
        rendered = str(host.render())

    assert "host-marker" in rendered
    # `{{ lazy_peer }}` and `{{ lazy_peer.html }}` each emit the peer's real
    # markup; `.props.label` emits the raw field value.
    assert rendered.count('<span class="peer-marker">hello</span>') == 2
    assert rendered.count("hello") == 3
    assert rendered.endswith("[hello]</section>")


def test_unreferenced_peers_do_not_render(tmp_path):
    """A registered peer nobody references must not be rendered (#67)."""

    (tmp_path / "quiet_host.html").write_text('<div class="quiet-marker"></div>')
    (tmp_path / "quiet_peer.html").write_text('<span class="loud-marker"></span>')
    module = _load_module(
        tmp_path,
        "quiet_defaults_components",
        "from pyjinhx import BaseComponent\n\n"
        "class QuietHost(BaseComponent):\n"
        "    pass\n\n"
        "class QuietPeer(BaseComponent):\n"
        "    pass\n",
    )

    Renderer.set_default_environment(str(tmp_path))

    with Registry.request_scope():
        module.QuietPeer(id="quiet_peer")
        rendered = str(module.QuietHost(id="quiet_host").render())

    assert "quiet-marker" in rendered
    assert "loud-marker" not in rendered


def test_build_render_context_does_not_copy_defaults():
    session = RenderSession()
    session.registry_defaults = {f"c{i}": object() for i in range(1000)}
    session.registry_scanned = 0

    with Registry.request_scope():
        render_context = renderer_module.build_render_context({"x": 1}, session)

    # The peers must not be materialized into the render context -- neither
    # individually nor behind a key holding the live, still-growing cache
    # (which `BaseComponent._build_template_context` would then walk while a
    # nested render mutates it).
    assert render_context == {"x": 1}
    assert session.registry_defaults not in render_context.values()

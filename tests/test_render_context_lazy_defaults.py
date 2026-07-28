"""Registry defaults must resolve lazily, not be copied per render (#240).

Peers used to be merged into every node's render context by id, which was
O(registered instances) per node. They are now resolved by name at the Jinja
layer (``renderer._PjxContext``), so the render context stays small -- but the
peer contract itself (``{{ peer }}`` / ``{{ peer.html }}`` /
``{{ peer.props.field }}``, deferred until referenced) must be unchanged.
"""

import importlib.util
import sys
from concurrent.futures import ThreadPoolExecutor

from jinja2 import Environment, FileSystemLoader

import pyjinhx.renderer as renderer_module
from pyjinhx import Renderer
from pyjinhx.assets import RenderSession
from pyjinhx.registry import Registry


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


def test_peer_resolves_inside_an_included_partial(tmp_path):
    """``{% include %}`` builds its own Jinja context; peers must still
    resolve inside it."""

    (tmp_path / "inc_partial.html").write_text("[{{ inc_peer }}]")
    (tmp_path / "inc_host.html").write_text(
        '<section class="host-marker">{% include "inc_partial.html" %}</section>'
    )
    (tmp_path / "inc_peer.html").write_text('<i class="peer-marker">{{ label }}</i>')
    module = _load_module(
        tmp_path,
        "include_defaults_components",
        "from pyjinhx import BaseComponent\n\n"
        "class IncHost(BaseComponent):\n"
        "    pass\n\n"
        "class IncPeer(BaseComponent):\n"
        "    label: str = ''\n",
    )

    Renderer.set_default_environment(str(tmp_path))

    with Registry.request_scope():
        module.IncPeer(id="inc_peer", label="hi")
        rendered = str(module.IncHost(id="inc_host").render())

    assert '[<i class="peer-marker">hi</i>]' in rendered


def test_explicit_context_shadows_same_named_peer(tmp_path):
    """A value the component actually declares still beats a registry peer of
    the same name, end to end."""

    (tmp_path / "shadow_host.html").write_text(
        '<section class="host-marker">[{{ shadow_peer }}]</section>'
    )
    (tmp_path / "shadow_peer.html").write_text('<i class="peer-marker">peer</i>')
    module = _load_module(
        tmp_path,
        "shadow_defaults_components",
        "from pyjinhx import BaseComponent\n\n"
        "class ShadowHost(BaseComponent):\n"
        "    shadow_peer: str = ''\n\n"
        "class ShadowPeer(BaseComponent):\n"
        "    pass\n",
    )

    Renderer.set_default_environment(str(tmp_path))

    with Registry.request_scope():
        module.ShadowPeer(id="shadow_peer")
        host = module.ShadowHost(id="shadow_host", shadow_peer="explicit")
        rendered = str(host.render())

    assert "[explicit]" in rendered
    assert "peer-marker" not in rendered


def test_peer_shadows_environment_global_of_the_same_name(tmp_path):
    """Peers used to be merged into the context `vars`, which Jinja layers on
    top of the globals -- so a peer named after a global still wins."""

    (tmp_path / "global_host.html").write_text(
        '<section class="host-marker">[{{ range }}]</section>'
    )
    (tmp_path / "global_peer.html").write_text('<i class="peer-marker">peer</i>')
    module = _load_module(
        tmp_path,
        "global_defaults_components",
        "from pyjinhx import BaseComponent\n\n"
        "class GlobalHost(BaseComponent):\n"
        "    pass\n\n"
        "class GlobalPeer(BaseComponent):\n"
        "    pass\n",
    )

    Renderer.set_default_environment(str(tmp_path))

    with Registry.request_scope():
        module.GlobalPeer(id="range")
        rendered = str(module.GlobalHost(id="global_host").render())

    assert '[<i class="peer-marker">peer</i>]' in rendered
    assert "class 'range'" not in rendered


def test_peer_shadows_environment_global_inside_a_derived_context(tmp_path):
    """`{% block ... scoped %}` (and other Jinja constructs, e.g. loop-scoped
    blocks) render through a *derived* ``Context`` (``Context.derived()``),
    built with ``globals=None``. Precedence must still match the non-derived
    case: a registered peer beats an environment/template global of the same
    name (#240)."""

    (tmp_path / "scoped_base.html").write_text(
        "{% for i in [1] %}{% block content scoped %}{% endblock %}{% endfor %}"
    )
    (tmp_path / "scoped_host.html").write_text(
        '{% extends "scoped_base.html" %}'
        "{% block content scoped %}"
        '<section class="host-marker">[{{ range }}]</section>'
        "{% endblock %}"
    )
    (tmp_path / "scoped_peer.html").write_text('<i class="peer-marker">peer</i>')
    module = _load_module(
        tmp_path,
        "scoped_defaults_components",
        "from pyjinhx import BaseComponent\n\n"
        "class ScopedHost(BaseComponent):\n"
        "    pass\n\n"
        "class ScopedPeer(BaseComponent):\n"
        "    pass\n",
    )

    Renderer.set_default_environment(str(tmp_path))

    with Registry.request_scope():
        module.ScopedPeer(id="range")
        rendered = str(module.ScopedHost(id="scoped_host").render())

    assert '[<i class="peer-marker">peer</i>]' in rendered
    assert "class 'range'" not in rendered


def test_async_environment_still_renders(tmp_path):
    """``enable_async=True`` environments are public API via
    ``Renderer(environment)``; rendering must not go down a sync-only path."""

    (tmp_path / "async_host.html").write_text('<b class="async-marker">{{ label }}</b>')
    module = _load_module(
        tmp_path,
        "async_defaults_components",
        "from pyjinhx import BaseComponent\n\n"
        "class AsyncHost(BaseComponent):\n"
        "    label: str = ''\n",
    )

    environment = Environment(
        loader=FileSystemLoader(str(tmp_path)), autoescape=True, enable_async=True
    )
    renderer = Renderer(environment)

    def render() -> str:
        with Registry.request_scope():
            host = module.AsyncHost(id="async_host", label="x")
            return str(host._render(_renderer=renderer))

    # In a worker thread: Jinja drives an async environment through
    # `asyncio.run`, which refuses to run inside an already-running event loop,
    # and other tests in the suite leave one on the main thread.
    with ThreadPoolExecutor(max_workers=1) as pool:
        rendered = pool.submit(render).result()

    assert '<b class="async-marker">x</b>' in rendered


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

"""Registry peers injected into render contexts are consumed lazily.

Repro for https://github.com/paulomtts/pyjinhx/issues/67 (finding 2) — every
registered instance is injected into every render context by id, and the
undeclared-keys loop in ``BaseComponent._render`` used to render all of them
eagerly. With N registered siblings whose template expands a tag, render counts
grew worse than factorially (N=4 -> 136 renders, N=5 -> 32k+), because tags
without an explicit id register new instances mid-render.

Peers must only render when a template actually references them, and the
referenced renders must keep the session-aware cycle guard.
"""

import importlib.util
import sys
import time

from pyjinhx import Registry
from pyjinhx.renderer import Renderer


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


def test_many_registered_peers_render_bounded(tmp_path, monkeypatch):
    """N registered Shell siblings: rendering one stays at a handful of renders."""

    (tmp_path / "explosion_shell.html").write_text(
        '<div class="shell-marker"><ExplosionInner/></div>'
    )
    (tmp_path / "explosion_inner.html").write_text('<span class="inner-marker">inner</span>')
    module = _load_module(
        tmp_path,
        "explosion_components",
        "from pyjinhx import BaseComponent\n\n"
        "class ExplosionShell(BaseComponent):\n"
        "    pass\n\n"
        "class ExplosionInner(BaseComponent):\n"
        "    pass\n",
    )

    Renderer.set_default_environment(str(tmp_path))

    calls = {"count": 0}
    original = Renderer.render_component_with_context

    def counting(self, *args, **kwargs):
        calls["count"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Renderer, "render_component_with_context", counting)

    sibling_count = 5
    with Registry.request_scope():
        shells = [module.ExplosionShell(id=f"shell_{i}") for i in range(sibling_count)]
        started = time.perf_counter()
        rendered = str(shells[0].render())
        elapsed = time.perf_counter() - started

    assert "shell-marker" in rendered
    assert "inner-marker" in rendered
    # Eager peer injection hit 32k+ renders here; lazy injection needs 2.
    assert calls["count"] <= 3 * sibling_count
    assert elapsed < 1.0


def test_lazy_peer_renders_when_template_references_it(tmp_path):
    """``{{ peer_id }}``, ``{{ peer_id.html }}`` and ``{{ peer_id.props.x }}``
    all keep working for injected peers."""

    (tmp_path / "ref_host.html").write_text(
        '<section class="host-marker"><RefChild id="ref_child"/></section>'
    )
    (tmp_path / "ref_child.html").write_text(
        '<div class="child-marker">{{ ref_peer }}|{{ ref_peer.html }}|{{ ref_peer.props.label }}</div>'
    )
    (tmp_path / "ref_peer.html").write_text('<span class="peer-marker">{{ label }}</span>')
    module = _load_module(
        tmp_path,
        "ref_components",
        "from pyjinhx import BaseComponent\n\n"
        "class RefHost(BaseComponent):\n"
        "    pass\n\n"
        "class RefChild(BaseComponent):\n"
        "    pass\n\n"
        "class RefPeer(BaseComponent):\n"
        "    label: str = ''\n",
    )

    Renderer.set_default_environment(str(tmp_path))

    with Registry.request_scope():
        module.RefPeer(id="ref_peer", label="hello")
        module.RefChild(id="ref_child")
        host = module.RefHost(id="ref_host")
        rendered = str(host.render())

    assert "host-marker" in rendered
    assert "child-marker" in rendered
    assert rendered.count("peer-marker") == 2  # {{ ref_peer }} and {{ ref_peer.html }}
    assert rendered.count("hello") == 3  # two rendered spans + props.label


def test_mutual_template_reference_by_id_is_cycle_guarded(tmp_path):
    """Two peers referencing each other via ``{{ id }}`` render once each;
    the cyclic back-reference renders empty instead of recursing forever."""

    (tmp_path / "jinja_cycle_host.html").write_text(
        '<main class="cycle-host-marker"><JinjaCycleLeft id="cycle_left"/></main>'
    )
    (tmp_path / "jinja_cycle_left.html").write_text(
        '<div class="left-marker">{{ cycle_right }}</div>'
    )
    (tmp_path / "jinja_cycle_right.html").write_text(
        '<p class="right-marker">{{ cycle_left }}</p>'
    )
    module = _load_module(
        tmp_path,
        "jinja_cycle_components",
        "from pyjinhx import BaseComponent\n\n"
        "class JinjaCycleHost(BaseComponent):\n"
        "    pass\n\n"
        "class JinjaCycleLeft(BaseComponent):\n"
        "    pass\n\n"
        "class JinjaCycleRight(BaseComponent):\n"
        "    pass\n",
    )

    Renderer.set_default_environment(str(tmp_path))

    with Registry.request_scope():
        module.JinjaCycleLeft(id="cycle_left")
        module.JinjaCycleRight(id="cycle_right")
        host = module.JinjaCycleHost(id="cycle_host")
        rendered = str(host.render())

    assert rendered.count("left-marker") == 1
    assert rendered.count("right-marker") == 1

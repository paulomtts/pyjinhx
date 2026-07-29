"""Root-attr stamping must not re-parse restored child markup (#240)."""

import pyjinhx.renderer as renderer_module
from pyjinhx import Renderer
from pyjinhx.registry import Registry


def _setup_container(tmp_path):
    (tmp_path / "box.html").write_text(
        '<div id="{{ id }}" class="box">{{ content }}</div>'
    )
    (tmp_path / "leaf.html").write_text('<span id="{{ id }}">{{ text }}</span>')
    Renderer.set_default_environment(str(tmp_path))
    return Renderer.get_default_renderer()


def test_container_root_scan_sees_opacified_markup(tmp_path, monkeypatch):
    renderer = _setup_container(tmp_path)

    seen_lengths: list[int] = []
    real_apply = renderer_module.apply_root_attrs

    def spying_apply(html, **kwargs):
        seen_lengths.append(len(html))
        return real_apply(html, **kwargs)

    monkeypatch.setattr(renderer_module, "apply_root_attrs", spying_apply)

    leaves = "".join(f'<Leaf id="l{i}" text="{"x" * 200}"></Leaf>' for i in range(50))
    with Registry.request_scope():
        out = renderer.render(f'<Box id="b">{leaves}</Box>')

    assert 'class="box"' in out
    assert out.count("<span") == 50
    # The Box-level root scan must have seen the collapsed (token) markup,
    # not the ~10KB of restored child spans. Generous bound: every
    # apply_root_attrs input stays far below the total child payload.
    assert max(seen_lengths) < 5000


def test_slot_only_template_still_errors_on_zero_roots(tmp_path):
    # A template whose entire body is the slot: opacified markup has no
    # element at all (root_count == 0); the fallback must restore and
    # succeed against the real child markup, preserving current behavior.
    (tmp_path / "bare.html").write_text("{{ content }}")
    (tmp_path / "leaf.html").write_text('<span id="{{ id }}">{{ text }}</span>')
    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    with Registry.request_scope():
        out = renderer.render('<Bare id="b"><Leaf id="l1" text="hi"></Leaf></Bare>')
    assert 'id="l1"' in out

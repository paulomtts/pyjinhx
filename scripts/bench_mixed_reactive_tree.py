"""Render benchmark: what a reactive node costs over a static one, same tree size.

bench_render_scaling_v2.py renders only plain BaseComponents;
bench_reactive_fanout.py measures the post-render walk, not the render itself.
Neither prices the one line where the two paths diverge: render_level() calls
child.pjx_mount() on every child it instantiates, unconditionally
(pyjinhx/render.py). On a BaseComponent that hook is a no-op; on a
ReactiveComponent it runs the cache-routed load(). So a page's reactive share,
not its node count, is what moves this cost — and nothing measured that.

Two arms, identical node counts and identical tree shape:

  * mixed: a plain static root and static mids, with reactive leaves.
  * pure: the same shape with every level reactive.

The delta between the arms is the mount cost of the levels that changed type,
with parse, context build and serialize held constant. Both arms run inside one
request_scope() so the load cache behaves as it does in a real request, and
each level is a distinct dynamically-named class (ADR 0004 cycle guard).

Not a CI test (timing-sensitive). Run manually before/after mount-path work:

    uv run python scripts/bench_mixed_reactive_tree.py
"""

import tempfile
import time
from pathlib import Path
from typing import Annotated

from pyjinhx import discovery
from pyjinhx.component import BaseComponent, _pascal_to_snake
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.reactive.component import PjxKey, ReactiveComponent
from pyjinhx.render import render
from pyjinhx.session import RenderSession, request_scope

SHAPES = ((5, 10), (10, 20), (20, 40), (30, 60))  # (mids, leaves per mid)


def _descriptor(cls: type[BaseComponent], template: str) -> ClassDescriptor:
    return ClassDescriptor(
        template_path=Path(template),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": cls},
    )


def build_arm(
    arm: str, reactive_levels: set[str], template_dir: Path
) -> type[BaseComponent]:
    """Build root/mid/leaf for one arm; levels named in ``reactive_levels`` are reactive.

    A reactive level gets a PjxKey field so load() is cache-keyed per instance,
    which is what a real reactive leaf looks like; a static level is a plain
    BaseComponent whose pjx_mount() is the inherited no-op.
    """
    names = {
        level: f"BenchMixed{arm}{level.capitalize()}"
        for level in ("root", "mid", "leaf")
    }
    classes: dict[str, type[BaseComponent]] = {}
    for level in ("leaf", "mid", "root"):
        namespace: dict[str, object] = {
            "label": "x",
            "__annotations__": {"label": str},
        }
        if level == "root":
            namespace["mids"] = 0
            namespace["leaves"] = 0
            namespace["__annotations__"].update({"mids": int, "leaves": int})  # type: ignore[union-attr]
        if level == "mid":
            namespace["leaves"] = 0
            namespace["__annotations__"]["leaves"] = int  # type: ignore[index]
        if level in reactive_levels:
            namespace["pjx_key"] = ""
            namespace["__annotations__"]["pjx_key"] = Annotated[str, PjxKey()]  # type: ignore[index]
            namespace["load"] = lambda self: f"data:{self.pjx_key}"
            base: type[BaseComponent] = ReactiveComponent
        else:
            base = BaseComponent
        classes[level] = type(names[level], (base,), namespace)

    sources = {
        "leaf": '<em class="mixed-leaf">{{ label }}</em>',
        "mid": (
            '<section class="mixed-mid">{{ label }}'
            "{% for j in range(leaves) %}"
            f'<{names["leaf"]} label="leaf" pjxKeyPlaceholder/>'
            "{% endfor %}</section>"
        ),
        "root": (
            '<div class="mixed-root">'
            "{% for i in range(mids) %}"
            f'<{names["mid"]} label="mid" leaves="{{{{ leaves }}}}" pjxKeyPlaceholder/>'
            "{% endfor %}</div>"
        ),
    }
    for level, source in sources.items():
        child_level = {"root": "mid", "mid": "leaf"}.get(level)
        key_attr = (
            ' pjx_key="{{ loop.index }}"' if child_level in reactive_levels else ""
        )
        source = source.replace(" pjxKeyPlaceholder", key_attr)
        template = f"{_pascal_to_snake(names[level])}.pjx"
        (template_dir / template).write_text(source)
        classes[level].__pjx_descriptor__ = _descriptor(classes[level], template)
        discovery._registry.mapping[_pascal_to_snake(names[level])] = classes[level]
    return classes["root"]


def bench(
    root_cls: type[BaseComponent],
    session: RenderSession,
    template_dir: str,
    mids: int,
    leaves: int,
) -> float:
    """``template_dir`` is threaded in explicitly, not read off ``session``:

    RenderSession.__init__ never stores its ``template_dir`` argument as an
    attribute (it only feeds it straight into the Jinja FileSystemLoader), so
    ``session.template_dir`` does not exist and would raise AttributeError.
    """
    with request_scope(template_dir):
        root = root_cls(mids=mids, leaves=leaves)
        t0 = time.perf_counter()
        out = render(root, session)
        dt = time.perf_counter() - t0
    assert out.count('class="mixed-leaf"') == mids * leaves, "unexpected leaf count"
    return dt


def main() -> None:
    template_dir = Path(tempfile.mkdtemp())
    discovery._registry.mapping = {}
    mixed_root = build_arm("Mixed", {"leaf"}, template_dir)
    pure_root = build_arm("Pure", {"root", "mid", "leaf"}, template_dir)
    session = RenderSession(template_dir=str(template_dir))
    template_dir_str = str(template_dir)

    bench(mixed_root, session, template_dir_str, 2, 2)  # warmup + sanity
    bench(pure_root, session, template_dir_str, 2, 2)

    print("static-ancestor vs. all-reactive tree, identical node counts:")
    print(f"{'nodes':>7}  {'mixed':>11}  {'pure':>11}  {'delta':>9}")
    for mids, leaves in SHAPES:
        nodes = 1 + mids + mids * leaves
        mixed = bench(mixed_root, session, template_dir_str, mids, leaves)
        pure = bench(pure_root, session, template_dir_str, mids, leaves)
        print(
            f"{nodes:7d}  {mixed * 1000:9.2f}ms  {pure * 1000:9.2f}ms  "
            f"{(pure - mixed) * 1000:7.2f}ms"
        )


if __name__ == "__main__":
    main()

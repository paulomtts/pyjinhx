"""Component-construction benchmark: declared field COUNT at a fixed tree shape.

Every sibling script builds components with two or three fields, so the
per-instance validation cost is a constant they never move. Two costs scale
with field count and are invisible there: _coerce_json_string_attrs
(pyjinhx/component.py), a "before" model validator that loops over every one
of cls.model_fields on every instantiation, and _instantiate_child
(pyjinhx/render.py), which copies a ChildRef's attrs dict and hands it to
pydantic. This script pins the tree shape and sweeps field count instead.

Two arms at each field count, so the JSON-coercion branch is measured rather
than assumed away:

  * plain: every field is typed str, so the coercion loop inspects each field
    and takes the cheap early-out.
  * json: every field is typed list, and each attr value is a JSON-looking
    string, so every field goes through json.loads.

The class at each field count is built dynamically with a distinct name (the
cycle guard's chain check, ADR 0004, is a name scan — reused names would
confound the reading, per bench_render_depth.py).

Not a CI test (timing-sensitive). Run manually before/after validator work:

    uv run python scripts/bench_field_count.py
"""

import os
import tempfile
import time
from pathlib import Path

from pyjinhx import discovery
from pyjinhx._component import BaseComponent, _pascal_to_snake
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

FIELD_COUNTS = (5, 20, 50, 100)

# CI runs these only to prove they still execute (tests/test_bench_scripts_smoke.py);
# timings are meaningless at one point, so the sweep collapses to its smallest.
if os.environ.get("PJX_BENCH_SMOKE"):
    FIELD_COUNTS = FIELD_COUNTS[:1]
FIXED_CHILDREN = 200


def _descriptor(
    cls: type[BaseComponent], template: str, template_dir: Path
) -> ClassDescriptor:
    return ClassDescriptor(
        template_path=template_dir / template,
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": cls},
    )


def build_pair(arm: str, fields: int, template_dir: Path) -> type[BaseComponent]:
    """Build a leaf with ``fields`` declared fields plus the root that spawns it.

    ``arm`` is "Plain" (str fields, coercion early-outs) or "Json" (list fields
    fed JSON-looking attr strings, so every field is parsed).
    """
    annotation = str if arm == "Plain" else list
    default: object = "" if arm == "Plain" else []
    leaf_name = f"BenchFieldCount{arm}Leaf{fields}"
    root_name = f"BenchFieldCount{arm}Root{fields}"
    namespace: dict[str, object] = {"__annotations__": {}}
    for i in range(fields):
        namespace[f"f{i}"] = default
        namespace["__annotations__"][f"f{i}"] = annotation  # type: ignore[index]
    leaf = type(leaf_name, (BaseComponent,), namespace)
    root = type(
        root_name,
        (BaseComponent,),
        {"count": 0, "__annotations__": {"count": int}},
    )
    (template_dir / f"{_pascal_to_snake(leaf_name)}.pjx").write_text(
        '<em class="leaf">{{ f0 }}</em>'
    )
    value = "x" if arm == "Plain" else "[1, 2, 3]"
    attrs = " ".join(f'f{i}="{value}"' for i in range(fields))
    (template_dir / f"{_pascal_to_snake(root_name)}.pjx").write_text(
        '<div class="root">{% for i in range(count) %}'
        f"<{leaf_name} {attrs}/>"
        "{% endfor %}</div>"
    )
    for cls in (leaf, root):
        cls.__pjx_descriptor__ = _descriptor(
            cls, f"{_pascal_to_snake(cls.__name__)}.pjx", template_dir
        )
        discovery._registry.mapping[_pascal_to_snake(cls.__name__)] = cls
    return root


def bench(root_cls: type[BaseComponent], session: RenderSession) -> float:
    root = root_cls(count=FIXED_CHILDREN)
    t0 = time.perf_counter()
    out = render(root, session)
    dt = time.perf_counter() - t0
    assert out.count('class="leaf"') == FIXED_CHILDREN, "unexpected child count"
    return dt


def main() -> None:
    template_dir = Path(tempfile.mkdtemp())
    discovery._registry.mapping = {}
    session = RenderSession()

    print(f"field-count sweep at a fixed {FIXED_CHILDREN} children per tree:")
    print(f"{'fields':>7}  {'plain':>11}  {'json':>11}  {'us/child (json)':>17}")
    for fields in FIELD_COUNTS:
        plain_root = build_pair("Plain", fields, template_dir)
        json_root = build_pair("Json", fields, template_dir)
        bench(plain_root, session)  # warmup + sanity, per shape
        plain = bench(plain_root, session)
        json_dt = bench(json_root, session)
        print(
            f"{fields:7d}  {plain * 1000:9.2f}ms  {json_dt * 1000:9.2f}ms  "
            f"{json_dt * 1e6 / FIXED_CHILDREN:15.1f}"
        )


if __name__ == "__main__":
    main()

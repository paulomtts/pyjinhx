"""L3.4.2 — the reactive on_rendered branch stamps data-pjx-id/data-pjx-hash.

Proof-of-work coverage only: that the subscriber stamps a ReactiveComponent's
root tag, no-ops on a plain one, carries state_hash() through unchanged, and
composes with an L0 pass-through stamp on the same RenderedLevel. The
exhaustive suite is #465.
"""

from pathlib import Path

import pytest

from pyjinhx2.component import BaseComponent
from pyjinhx2.descriptor import ClassDescriptor
from pyjinhx2.reactive.component import ReactiveComponent
from pyjinhx2.reactive.root_attrs import stamp_reactive_root_attrs
from pyjinhx2.render import render_level
from pyjinhx2.root_attrs import stamp_root_attrs
from pyjinhx2.segments import serialize
from pyjinhx2.session import RenderSession


class ReactiveWidget(ReactiveComponent):
    title: str = "hello"


class PlainWidget(BaseComponent):
    pass


def _descriptor_for(cls: type[BaseComponent], template: str) -> ClassDescriptor:
    return ClassDescriptor(
        template_path=Path(template),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": cls},
    )


ReactiveWidget.__pjx_descriptor__ = _descriptor_for(ReactiveWidget, "reactive_widget.html")
PlainWidget.__pjx_descriptor__ = _descriptor_for(PlainWidget, "plain_widget.html")


@pytest.fixture
def session() -> RenderSession:
    """A session with only the reactive root-attr subscriber attached."""
    session = RenderSession(template_dir="tests/templates")
    session.on_rendered.append(stamp_reactive_root_attrs)
    return session


def test_reactive_root_tag_carries_id_and_hash(session: RenderSession):
    component = ReactiveWidget(id="w1")

    html = serialize(render_level(component, session))

    assert 'data-pjx-id="w1"' in html
    assert f'data-pjx-hash="{component.state_hash()}"' in html


def test_stamped_hash_is_exactly_state_hash(session: RenderSession):
    """No recompute drift: the stamped digest is the one state_hash() returns."""
    component = ReactiveWidget(id="w2", title="different")

    html = serialize(render_level(component, session))

    stamped = html.split('data-pjx-hash="')[1].split('"')[0]
    assert stamped == component.state_hash()


def test_plain_component_root_tag_is_untouched(session: RenderSession):
    html = serialize(render_level(PlainWidget(id="p1"), session))

    assert "data-pjx-id" not in html
    assert "data-pjx-hash" not in html
    assert html == "<em>plain</em>"


def test_composes_with_a_pass_through_stamp_on_the_same_level(session: RenderSession):
    """L0 stamping still works alongside the reactive branch: the pass-through
    attr survives, and neither attribute is written twice."""
    component = ReactiveWidget(id="w3")

    level = render_level(component, session)
    stamp_root_attrs(level, {"class": "card"})
    html = serialize(level)

    assert 'class="card"' in html
    assert 'data-pjx-id="w3"' in html
    assert html.count("data-pjx-id=") == 1
    assert html.count("data-pjx-hash=") == 1


def test_re_stamping_the_same_level_overrides_rather_than_duplicates(
    session: RenderSession,
):
    """emit_rendered fires once per component, but the subscriber must still be
    idempotent against the override semantics stamp_root_attrs already has."""
    component = ReactiveWidget(id="w4")

    level = render_level(component, session)
    stamp_reactive_root_attrs(component, level, session)
    html = serialize(level)

    assert html.count("data-pjx-id=") == 1
    assert html.count("data-pjx-hash=") == 1

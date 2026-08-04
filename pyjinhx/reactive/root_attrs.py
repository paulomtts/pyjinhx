"""The reactive branch of ``on_rendered``: stamp id + state hash on the root tag.

Lives under reactive/ because the import rule runs one way — reactive/ may
import the spine (session, segments, root_attrs), never the reverse. The
subscriber is exported, not auto-registered: callers append it to
``RenderSession.on_rendered``, exactly like ``accumulate_assets`` and
``register_rendered_instance``.
"""

from pyjinhx._component import BaseComponent, _pascal_to_snake
from pyjinhx.reactive.component import ReactiveComponent
from pyjinhx.reactive.keys import coerce_load_key_str
from pyjinhx.root_attrs import stamp_root_attrs
from pyjinhx.segments import RenderedLevel
from pyjinhx.session import RenderSession


def stamp_reactive_root_attrs(
    component: BaseComponent, level: RenderedLevel, session: RenderSession
) -> None:
    """Splice ``data-pjx-id``/``-type``/``-load``/``-hash`` onto a reactive component's root tag.

    Shaped for ``RenderSession.on_rendered``. A non-reactive component returns
    before anything is read or built, so a tree with no reactive nodes pays one
    isinstance check per component and nothing else.

    ``type``/``load`` are what ``pjx.js``'s manifest builder reads back into
    ``X-PJX-Mounted`` entries and what ``fanout.py``'s ``walk_manifest`` keys
    its clean/dirty resolution on (fanout.py:9, :81) — without them a real
    client-built manifest carries empty fields and the walk drops everything.

    Args:
        component: The component that just finished rendering.
        level: That component's RenderedLevel, stamped in place at its root_span.
        session: The RenderSession this render ran against (unused; on_rendered's
            callback shape always passes it).
    """
    if not isinstance(component, ReactiveComponent):
        return
    attrs = {
        "data-pjx-id": component.id,
        "data-pjx-type": _pascal_to_snake(type(component).__name__),
        # state_hash() reads only the instance's own fields, so calling it here
        # cannot trigger a load() or perturb the render that just finished.
        "data-pjx-hash": component.state_hash(),
    }
    field = component._pjx_key_field
    if field is not None:
        load_key = coerce_load_key_str(getattr(component, field, None))
        if load_key is not None:
            attrs["data-pjx-load"] = load_key
    stamp_root_attrs(level, attrs)

"""How a rendered level is keyed for the tier-2 (non-reactive) render cache.

Stateless by construction: one pure function over a component instance and the
template file its class resolved to. Storing and restoring entries under this
key lives elsewhere.
"""

import hashlib
import json

from pyjinhx._component import BaseComponent


def _holds_component(value: object) -> bool:
    """True when a slot/children field's current value will be spliced back in
    as a ``ChildRef`` rather than baked into the cached segments as text.

    A bare component, or a list/dict holding at least one, qualifies; a plain
    string on the same field does not, even though the field's declared type
    permits both.
    """
    if isinstance(value, BaseComponent):
        return True
    if isinstance(value, list):
        return any(isinstance(item, BaseComponent) for item in value)
    if isinstance(value, dict):
        return any(isinstance(item, BaseComponent) for item in value.values())
    return False


def render_cache_key(component: BaseComponent) -> str:
    """Return the render-cache key for ``component``.

    Three parts joined by ``:`` — the fully qualified class name, a SHA-256
    digest of the instance's own field values with component-bearing slot and
    children values left out (a string on the same field stays in, since it is
    baked into the cached output rather than spliced back in), and the
    modification time of the template the class resolved to.
    """
    cls = type(component)
    descriptor = cls.__pjx_descriptor__
    identity = f"{cls.__module__}.{cls.__qualname__}"
    # Slot/children fields whose live value is a component (or a list/dict of
    # them) are rendered as opaque holes and spliced back in after a hit -
    # hashing them would make the key vary per request and never hit for the
    # shell that is the whole point of caching. The same field holding a plain
    # string instead is baked into the cached segments as literal text, never
    # a ChildRef, so that value has to stay in the key or two different
    # strings on the same field would collide on one entry.
    hole_fields = set(descriptor.slot_fields)
    if descriptor.children_field is not None:
        hole_fields.add(descriptor.children_field)
    spliced_fields = {
        name for name in hole_fields if _holds_component(getattr(component, name))
    }
    # JSON-mode dump plus sorted, separator-pinned encoding so dict ordering
    # and non-JSON-native types can't perturb an unchanged set of props.
    canonical = json.dumps(
        component.model_dump(mode="json", exclude=spliced_fields),
        sort_keys=True,
        separators=(",", ":"),
    )
    fields_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    # Left to raise: a key that silently drops the template part would serve a
    # stale level forever after an author edits that template, and no restart
    # would clear it.
    template_mtime = descriptor.template_path.stat().st_mtime
    return f"{identity}:{fields_digest}:{template_mtime}"

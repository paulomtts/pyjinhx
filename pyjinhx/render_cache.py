"""How a rendered level is keyed, stored and restored for the tier-2
(non-reactive) render cache.
"""

import hashlib
import json
from typing import TYPE_CHECKING, Any

from pyjinhx._component import BaseComponent
from pyjinhx.reactive.backend import MISS, CacheBackend
from pyjinhx.segments import ChildRef, RenderedLevel

if TYPE_CHECKING:
    from pyjinhx.session import RenderSession


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


def store_rendered_level(
    backend: CacheBackend, key: str, level: RenderedLevel, *, ttl: float | None
) -> None:
    """Put ``level`` into ``backend`` under ``key``, expiring after ``ttl`` seconds.

    Args:
        backend: The tier-2 store to write behind.
        key: The entry's key, as answered by ``render_cache_key``.
        level: The level to cache, with its child holes still unresolved.
        ttl: Seconds the entry stays valid, or None to never expire on its own.
    """
    # Untagged on purpose: tags exist so a dirtied reactive key can evict what
    # it invalidated, and a non-reactive level has no reactive key behind it.
    # Its only invalidation paths are the template mtime baked into the key and
    # the ttl.
    backend.put(key, level, tags=(), ttl=ttl)


def restore_rendered_level(backend: CacheBackend, key: str) -> object:
    """Return the level stored under ``key``, or ``MISS``.

    Args:
        backend: The tier-2 store to read through.
        key: The entry's key, as answered by ``render_cache_key``.

    Returns:
        The restored RenderedLevel on a hit, or ``MISS`` when there is no live
        entry.

    Raises:
        ValueError: If the entry exists but is not shaped like a RenderedLevel.
    """
    value = backend.get(key)
    if value is MISS:
        return MISS
    # A hit that does not look like a level is a corrupted or foreign entry,
    # and answering MISS for it would quietly re-render forever while the bad
    # entry sat there; answering it as-is would splice something unserializable
    # into a page. Neither is a thing a caller can notice, so it raises.
    _check_restored(key, value)
    return value


def _check_restored(key: str, value: object) -> None:
    """Raise unless ``value`` is a RenderedLevel whose parts survived storage."""
    # ValueError, not TypeError (ruff TRY004 would prefer): this is a data
    # integrity problem with a stored entry, not a caller passing the wrong
    # type into a function.
    if not isinstance(value, RenderedLevel):
        raise ValueError(  # noqa: TRY004
            f"render cache entry {key!r} is not a RenderedLevel but a "
            f"{type(value).__name__}; the entry is corrupt or was written by "
            f"something else, and serving it would put that value in a page."
        )
    for index, segment in enumerate(value.segments):
        if not isinstance(segment, (str, ChildRef, RenderedLevel)):
            raise ValueError(  # noqa: TRY004
                f"render cache entry {key!r} came back with segment {index} as a "
                f"{type(segment).__name__}; a level's segments are str, ChildRef "
                f"or RenderedLevel only, so this entry did not survive storage."
            )


def replay_asset_accumulation(level: RenderedLevel, session: "RenderSession") -> None:
    """Set-add a restored level's descriptor asset paths into ``session``.

    A cache hit never runs render_level, so the on_rendered fan-out that
    normally collects assets never fires. This replays that one subscriber's
    effect and nothing else: the other two subscribers stamp reactive root
    attrs and register a reactive instance, and tier 2 only ever holds
    non-reactive components, so firing them here would invent state for a
    component that has none.

    Args:
        level: The restored level whose descriptor carries the asset paths.
        session: The RenderSession this request is rendering against.
    """
    # Same structural read as session.accumulate_assets: RenderedLevel.descriptor
    # is typed as `object` to keep segments.py import-pure, and importing
    # ClassDescriptor here just to annotate it would break that parity for
    # nothing.
    descriptor: Any = level.descriptor
    session.css_assets.update(descriptor.css_paths)
    session.js_assets.update(descriptor.js_paths)

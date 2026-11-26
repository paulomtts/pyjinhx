"""How a rendered level is keyed, stored and restored for the tier-2
(non-reactive) render cache.
"""

import hashlib
import json
import os
from typing import TYPE_CHECKING, Any, cast

from pyjinhx._component import BaseComponent
from pyjinhx.reactive.backend import MISS, CacheBackend, CachePolicy
from pyjinhx.reactive.backend_health import (
    is_degraded,
    note_failure,
    note_write_success,
)
from pyjinhx.segments import ChildRef, RenderedLevel

if TYPE_CHECKING:
    from pyjinhx.session import RenderSession

# A cache hit is not free: the key, the backend read, the unpickle and the asset
# replay come to roughly 20us for a small component. Caching a render cheaper
# than that costs more than it saves, and every builtin this repo ships renders
# in 30-105us with only a fraction of that spent on the template. The default
# sits well clear of them, so what gets cached is a template doing real work.
_DEFAULT_MIN_SAVING_US = 150.0

# Qualified names, not classes: see _too_cheap_key. Process-wide because the
# measurement is a property of the template, not of any one request.
_too_cheap: set[str] = set()
_decided: set[str] = set()


def reset_render_cost_decisions() -> None:
    """Forget every measured class. For tests, which must not inherit a verdict."""
    _too_cheap.clear()
    _decided.clear()


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


def _spliced_fields(component: BaseComponent) -> set[str]:
    """Slot/children field names whose current value is a component, or a
    list/dict holding one.

    These are the fields a render treats as opaque holes: the key leaves them
    out (see render_cache_key) and the cache refuses the instance outright (see
    holds_spliced_components), which are the two halves of one rule.
    """
    descriptor = type(component).__pjx_descriptor__
    hole_fields = set(descriptor.slot_fields)
    if descriptor.children_field is not None:
        hole_fields.add(descriptor.children_field)
    return {name for name in hole_fields if _holds_component(getattr(component, name))}


def holds_spliced_components(component: BaseComponent) -> bool:
    """Whether this instance carries a component in a slot or children field,
    which disqualifies it from the render cache.

    Such a value never reaches the template as text: build_context wraps it in a
    ComponentNode, and interpolating it fires the finalize hook, which writes a
    random ``pjx-slot-<uuid4 hex>`` token into a table that lives exactly as long
    as the one ``template.render()`` call that produced it. A cache hit performs
    no such call, so the tokens baked into a restored level match nothing in this
    request and would splice as literal garbage into the page.

    Regenerating those tokens positionally against a fresh table is possible in
    principle - an identical key implies identical control flow implies identical
    emission order - but it needs the stored level to carry that order, which
    means changing what is stored. So the render cache declines these instances
    instead, the same way the load cache declines an unpicklable result: not an
    error, just an instance that renders live every time.

    Answered per instance, not per class: a Slot field declared component-capable
    but currently holding a plain string emits no token at all, and that string is
    baked into the cached segments as text (and stays in the key), so there is
    nothing to disqualify.
    """
    return bool(_spliced_fields(component))


def has_auto_id(component: BaseComponent) -> bool:
    """Whether this instance's ``id`` came from the default factory.

    Pydantic records the names the caller actually passed in ``model_fields_set``,
    so an absent ``id`` there is one ``_auto_id()`` minted — ``pjx-1``, ``pjx-2``,
    and so on, a fresh value per instance.
    """
    return "id" not in component.model_fields_set


def auto_id_in_output(component: BaseComponent, output: str) -> bool:
    """Whether an auto-generated ``id`` was interpolated into this render.

    The key deliberately ignores an auto id, so a template that prints one — via
    ``{{ id }}``, or an attribute built from it — would bake ``pjx-1`` into an
    entry later served to ``pjx-2``. Such an instance is declined rather than
    cached wrong, the same way ``holds_spliced_components`` declines one whose
    slot tokens cannot outlive their render.

    Tested against the finished output rather than by parsing the template for
    an ``id`` reference: the output is the ground truth about what actually got
    printed, it is already in hand at the point this is asked, and a substring
    scan costs far less than a second parse. An author-supplied id is not
    checked at all — it is in the key, so an entry can only ever be served back
    to the same value.

    Args:
        component: The instance that produced ``output``.
        output: The template's rendered text, before parsing.
    """
    if not has_auto_id(component):
        return False
    return component.id in output


def render_cache_key(component: BaseComponent) -> str:
    """Return the render-cache key for ``component``.

    Three parts joined by ``:`` — the fully qualified class name, a SHA-256
    digest of the instance's own field values with component-bearing slot and
    children values left out (a string on the same field stays in, since it is
    baked into the cached output rather than spliced back in), and the
    modification time of the template the class resolved to.

    An auto-generated ``id`` is left out of the digest too. It counts up per
    instance, so keeping it would give two structurally identical components two
    different keys and the cache could never hit at all. An id the author passed
    explicitly stays in: that one names something about the instance, and two
    values of it are two different renders. This mirrors reactive's
    ``state_hash_exclude``, which drops ``id`` for the same reason.
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
    spliced_fields = _spliced_fields(component)
    if has_auto_id(component):
        spliced_fields.add("id")
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


def _min_saving_us() -> float:
    """The render-and-parse cost, in microseconds, below which caching is a loss.

    Read per call rather than captured at import so a test — or an app that sets
    the variable after importing pyjinhx — is not fighting import order.
    """
    raw = os.environ.get("PJX_RENDER_CACHE_MIN_US")
    if raw is None or raw == "":
        return _DEFAULT_MIN_SAVING_US
    try:
        return float(raw)
    except ValueError:
        raise ValueError(
            f"PJX_RENDER_CACHE_MIN_US={raw!r} is not a number of microseconds."
        ) from None


def is_too_cheap(cls: type[BaseComponent]) -> bool:
    """Whether this class was measured as costing less to render than to cache.

    Answered from a process-wide set filled by ``note_render_cost``. Asked before
    the key is built and before the backend is read, because a class that is not
    worth caching should pay neither — skipping only the write would leave the
    per-request half of the waste in place.
    """
    return _too_cheap_key(cls) in _too_cheap


def note_render_cost(cls: type[BaseComponent], saving_us: float) -> None:
    """Record what rendering this class actually cost, and decide it once.

    ``saving_us`` is the template render plus the parse — the work a cache hit
    replaces, not the whole of render_level. Timing the whole thing would fold in
    validation, context building and child filling, none of which a hit avoids,
    and would price a class as expensive for work the cache cannot save.

    Per class rather than per instance: the same template doing the same work
    costs the same whether it is row 3 or row 197, so one measurement settles
    every instance and the check afterwards is a set lookup.

    Decided once and never revisited. A class that re-measured could flip between
    requests on nothing but machine load, which would make cache membership — and
    so the store's contents — depend on scheduling noise.
    """
    key = _too_cheap_key(cls)
    if key in _decided:
        return
    _decided.add(key)
    if saving_us < _min_saving_us():
        _too_cheap.add(key)


def _too_cheap_key(cls: type[BaseComponent]) -> str:
    """The qualified name this class is remembered under.

    A name rather than the class object, so the two sets cannot keep a class
    alive for the life of the process — the same reason the diskcache backend
    remembers unpicklable types by name.
    """
    return f"{cls.__module__}.{cls.__qualname__}"


def resolve_render_tier2(
    cls: type[BaseComponent],
) -> tuple[CacheBackend | None, float | None]:
    """The render cache this class stores through, and the ttl it writes at.

    Answers ``(None, None)`` when the render cache is off for ``cls`` - either
    because no backend is configured for the process or because the class opted
    out with ``cache=False``. Otherwise the configured backend and the seconds
    its entries stay valid.

    A near-twin of reactive's ``_resolve_tier2`` rather than a shared import:
    that one is typed to ReactiveComponent and lives next to the load-cache key
    machinery its only caller needs, while this one is handed a plain class and
    nothing else. Sharing them would drag reactive/ into the render spine's
    reach for four lines.
    """
    # Function-local by necessity: config sits above the render spine and
    # imports it at import time, so a module-scope edge back would be a real
    # cycle. Same escape hatch reactive's _resolve_tier2 uses.
    from pyjinhx.config import current_settings

    policy = cls._pjx_cache_policy
    # `is False`, not falsiness: None is "the class said nothing", which means
    # the process default applies, and it is not the same answer as an explicit
    # opt-out.
    if policy is False:
        return None, None
    backend = current_settings().cache_backend
    if backend is None:
        return None, None
    return backend, (CachePolicy() if policy is None else policy).ttl


def copy_level_shell(level: RenderedLevel) -> RenderedLevel:
    """A level sharing everything but its segment list with ``level``.

    Both directions across the cache seam need this. A backend may store by
    reference (InMemoryCacheBackend does, by design), while _fill_children and
    _splice_slot_nodes rewrite ``segments`` in place - so writing the live level
    would let this request's children land inside the cached entry, and handing
    a restored entry straight back would let the next request fill a level that
    is already full.

    Shallow on purpose: the descriptor is frozen, the root span is a tuple, and
    a ChildRef is only ever read (its attrs are copied before use), so a deep
    copy would duplicate immutable data on every hit for nothing.
    """
    return RenderedLevel(
        segments=list(level.segments),
        root_span=level.root_span,
        descriptor=level.descriptor,
    )


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


def load_rendered_level(backend: CacheBackend, key: str) -> RenderedLevel | None:
    """The level cached under ``key``, or None when there is nothing usable.

    None covers three answers the caller treats identically - no entry, a
    degraded backend that is not being read from, and a backend whose get()
    raised - because all three mean the same thing to a render: do the work.

    The level comes back detached from the stored one (copy_level_shell), so the
    caller may fill its children without editing the cache.

    Raises:
        ValueError: If the entry exists but is not a RenderedLevel. A corrupt or
            foreign entry is a data-integrity problem the caller must see, not a
            backend that failed to answer, so it is neither swallowed as a miss
            nor counted against the backend's health.
    """
    # A degraded backend is one whose evict() raised: entries it still holds may
    # be stale, so it is not read from until a write lands.
    if is_degraded(backend):
        return None
    try:
        restored = restore_rendered_level(backend, key)
    except ValueError:
        raise
    # A backend is a plugin implementing an arbitrary protocol, so its failure
    # mode is unknowable in advance; the policy is to degrade on any of them
    # rather than pick and miss some.
    except Exception as exc:  # noqa: BLE001
        # A cache is an optimization: a backend that cannot answer costs this
        # request a real render, never an error.
        note_failure(backend, "get", exc, degrade=False)
        return None
    if restored is MISS:
        return None
    return copy_level_shell(cast(RenderedLevel, restored))


def save_rendered_level(
    backend: CacheBackend, key: str, level: RenderedLevel, *, ttl: float | None
) -> None:
    """Write ``level``'s shell behind ``key``, absorbing a backend that raises.

    Stores a detached copy: the caller is about to resolve this level's children
    in place, and the entry must keep its holes for the next request to fill.
    """
    try:
        store_rendered_level(backend, key, copy_level_shell(level), ttl=ttl)
    # Same rationale as the get() guard above: any backend failure degrades
    # rather than only the ones this module can predict.
    except Exception as exc:  # noqa: BLE001
        # The level is already rendered: a dropped write costs the next request
        # a render, nothing more.
        note_failure(backend, "put", exc, degrade=False)
    else:
        # A write that landed is the evidence a degraded backend is answering
        # again, and that what it now holds is current.
        note_write_success(backend)

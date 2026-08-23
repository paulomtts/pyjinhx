"""The request-scoped instance registry: composite keys, resolve, and the writer.

Entries are written by the Load path through register_instance(), the module's
single mutator; make_key() and resolve() only read. Callers on the Load path are
expected to dedup by (type, load_arg) before loading — that is a Load-path
concern, not this module's, and resolve() deduplicates nothing.
"""

import logging
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from pyjinhx.session import (
    _instances,
    _quiet_collisions,
    get_dev_strict,
    get_instances,
    get_quiet_collisions,
)

if TYPE_CHECKING:
    # Type-only: naming the spine's own types in a signature must not make this
    # module import its consumers at runtime.
    from pyjinhx.segments import RenderedLevel
    from pyjinhx.session import RenderSession

logger = logging.getLogger("pyjinhx")


def make_key(type_name: str, instance_id: str) -> str:
    """Build the composite registry key for a component type and instance id.

    Args:
        type_name: The component type's name.
        instance_id: The instance's id, unique within one request.

    Returns:
        The composite key, e.g. ``"PJXButton_btn1"``.
    """
    return f"{type_name}_{instance_id}"


def resolve(type_name: str, instance_id: str) -> object:
    """Return the entry registered under this request's composite key.

    Args:
        type_name: The component type's name.
        instance_id: The instance's id.

    Returns:
        Whatever the Load path stored — a live instance or a cached
        RenderedLevel — returned as-is, never re-derived or re-parsed.

    Raises:
        LookupError: The key is not registered in this request, including
            every key when called outside an active request_scope().
    """
    key = make_key(type_name, instance_id)
    # get_instances() answers {} outside a scope, so an out-of-scope call is a
    # plain miss rather than a distinct error — one lookup, one failure mode.
    instances = get_instances()
    if key not in instances:
        raise LookupError(f"No instance registered under key {key!r}")
    return instances[key]


class InstanceKeyCollisionError(RuntimeError):
    """Two live entries claimed one composite key within a single request.

    Not a LookupError: ADR 0009 reserves that for resolve() misses, which are a
    read-side failure. This is a write-side one, and it only surfaces while
    reactive-dev strict mode is on.
    """


@contextmanager
def quiet_collisions(keys: Iterable[str]) -> Iterator[None]:
    """Mark composite keys whose collision is expected for the duration of the block.

    A write to one of these keys still overwrites — last-write-wins is
    unchanged — but skips the warning and the dev-strict raise. Nested blocks
    union: an inner block adds to the outer one's set, and the exit restores the
    outer one exactly, including when the body raises. Used outside an active
    request_scope() this binds and restores a set nothing reads, which is a
    no-op rather than an error: the mechanism is advisory noise-suppression.

    Args:
        keys: Composite keys, as make_key() builds them.

    Yields:
        None; the block body runs with those keys quieted.
    """
    token = _quiet_collisions.set(get_quiet_collisions() | frozenset(keys))
    try:
        yield
    finally:
        # Reset by token, never by assigning the old value back: a worker's
        # copied context and a nested block both have to hand back exactly what
        # they were handed, and only the token knows what that was.
        _quiet_collisions.reset(token)


def register_instance(type_name: str, instance_id: str, entry: object) -> None:
    """Store an entry in this request's registry under its composite key.

    The only function that mutates the registry: resolve() and every other
    reader leaves the store untouched.

    Args:
        type_name: The component type's name.
        instance_id: The instance's id, unique within one request.
        entry: What resolve() should hand back — a live instance or a cached
            RenderedLevel, stored as-is.

    Raises:
        InstanceKeyCollisionError: The key already holds an entry in this
            request, reactive-dev strict mode is on, and the key is not one an
            enclosing quiet_collisions() block marked as expected. With strict
            mode off the collision is a warning; quieted, it is silent. Either
            way the write itself is a last-write-wins overwrite.
    """
    key = make_key(type_name, instance_id)
    # get_instances() answers a throwaway {} outside a scope, so writing there
    # would silently vanish; say so instead of pretending the entry landed.
    instances = get_instances()
    if not instances and _instances.get() is None:
        logger.warning(
            "Entry for key %r registered outside request_scope(); dropped.", key
        )
        return
    if key in instances and key not in get_quiet_collisions():
        # The one production caller fires once per rendered component, so a
        # second write to one key in one request means two components claimed
        # the same id — usually a hard-coded `id` default on a class rendered
        # more than once. Unless a caller said otherwise: a key inside an
        # active quiet_collisions() block is one this request already knows two
        # builds will claim (#1022 — a region rendered both as its own fan-out
        # candidate and as a nested descendant of a sibling candidate's tree),
        # so it overwrites in silence.
        if get_dev_strict():
            raise InstanceKeyCollisionError(
                f"Key {key!r} is already registered; two instances share one id."
            )
        logger.warning("Key %r is already registered; overwriting.", key)
    instances[key] = entry


def register_rendered_instance(
    component: Any, level: "RenderedLevel", session: "RenderSession"
) -> None:
    """Register a just-rendered component's level under its composite key.

    Shaped for ``RenderSession.on_rendered`` and subscribed onto every request's
    session by ``integrations/fastapi.py``'s middleware; a hand-built session
    that never attaches it registers nothing.

    Args:
        component: The component that was just rendered; its class name and
            ``id`` form the composite key.
        level: That component's RenderedLevel, stored as the entry.
        session: The RenderSession this render ran against (unused; on_rendered's
            callback shape always passes it).
    """
    register_instance(type(component).__name__, component.id, level)

"""The request-scoped instance registry: composite keys, resolve, and the writer.

Entries are written by the Load path through register_instance(), the module's
single mutator; make_key() and resolve() only read. Callers on the Load path are
expected to dedup by (type, load_arg) before loading — that is a Load-path
concern, not this module's, and resolve() deduplicates nothing.
"""

import logging

from pyjinhx2.session import _instances, get_instances

logger = logging.getLogger("pyjinhx2")


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


def register_instance(type_name: str, instance_id: str, entry: object) -> None:
    """Store an entry in this request's registry under its composite key.

    The only function that mutates the registry: resolve() and every other
    reader leaves the store untouched.

    Args:
        type_name: The component type's name.
        instance_id: The instance's id, unique within one request.
        entry: What resolve() should hand back — a live instance or a cached
            RenderedLevel, stored as-is.
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
    if key in instances:
        logger.warning("Key %r is already registered; overwriting.", key)
    instances[key] = entry

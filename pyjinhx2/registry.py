"""The request-scoped instance registry: composite keys and read-only resolve.

Read side only (ADR 0009). Entries are written by the Load path (#435); nothing
here mutates the store. Callers on the Load path are expected to dedup by
(type, load_arg) before loading — that is a Load-path concern, not this
module's, and resolve() deduplicates nothing.
"""

from pyjinhx2.session import get_instances


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

from __future__ import annotations

from collections.abc import Callable

from markupsafe import Markup

from .backend import ClientBackend
from .dev import warn_reactive_render_without_client
from .load_cache import LoadCache
from .mutations import MutationTracker
from .oob import oob_swaps
from .payload import MountedManifest, TriggerManifest


def _reactive_context_active() -> bool:
    backend = ClientBackend.current()
    if backend is None:
        return False
    if MutationTracker.pending():
        return True
    return bool(MountedManifest.parse(backend))


def reactive_render_bundle(
    *,
    primary_html: Markup | Callable[[], Markup | str],
    exclude_ids: set[str] | Callable[[], set[str]],
    invalidate_before_primary: bool,
) -> Markup:
    """
    Shared reactive render orchestration for class and instance ``render()`` paths.
    """
    backend = ClientBackend.current()
    warn_reactive_render_without_client(backend=backend)

    effective_dirtied = MutationTracker.pending()
    if invalidate_before_primary:
        LoadCache.invalidate(effective_dirtied)

    primary = primary_html() if callable(primary_html) else primary_html
    MutationTracker.mark_render_consumed()

    resolved_exclude = set(exclude_ids() if callable(exclude_ids) else exclude_ids)
    trigger = TriggerManifest.parse(backend) if backend is not None else None
    if trigger and trigger.get("id"):
        resolved_exclude.add(str(trigger["id"]))

    swaps = oob_swaps(
        effective_dirtied,
        backend,
        exclude_ids=resolved_exclude,
        skip_invalidate=invalidate_before_primary,
    )
    return Markup(primary) + swaps

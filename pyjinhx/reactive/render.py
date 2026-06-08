from __future__ import annotations

from collections.abc import Callable

from markupsafe import Markup

from pyjinhx.reactive.keys import ReactiveKey

from .dev import warn_reactive_render_without_mounted
from .load_cache import LoadCache
from .mutations import MutationTracker
from .oob import oob_swaps


def reactive_render_bundle(
    *,
    primary_html: Markup | Callable[[], Markup | str],
    own_keys: set[str],
    dirtied: set[ReactiveKey] | None,
    mounted: object | None,
    exclude_ids: set[str] | Callable[[], set[str]],
    invalidate_before_primary: bool,
) -> Markup:
    """
    Shared reactive render orchestration for class and instance ``render()`` paths.

    When ``invalidate_before_primary`` is True (class render), the load cache is
    evicted before the primary is built and OOB swaps skip a second invalidation.
    When False (instance render), invalidation happens inside ``oob_swaps``.
    """
    warn_reactive_render_without_mounted(
        dirtied=dirtied, mounted=mounted, own_keys=own_keys
    )
    effective_dirtied = MutationTracker.resolve_effective_dirtied(
        dirtied=dirtied,
        mounted=mounted,
        own_keys=own_keys,
    )
    if invalidate_before_primary:
        LoadCache.invalidate(effective_dirtied | own_keys)

    primary = primary_html() if callable(primary_html) else primary_html
    MutationTracker.mark_render_consumed()
    resolved_exclude = exclude_ids() if callable(exclude_ids) else exclude_ids
    swaps = oob_swaps(
        effective_dirtied,
        mounted,
        exclude_ids=resolved_exclude,
        skip_invalidate=invalidate_before_primary,
    )
    return Markup(primary) + swaps

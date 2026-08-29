"""The asset delta: which of a fan-out's assets the client does not have yet.

An OOB region swap carries markup only. A region that is being swapped in for
the first time in this page's life still needs its stylesheet and its script,
and the client tells the server which ones it already has in ``X-PJX-Assets``.
This module answers the difference, as head-targeted OOB fragments pjx.js
relocates on arrival (``pyjinhx/client/pjx.js`` reads ``data-pjx-asset``).

Ported from v0.x's ``render_missing_assets_oob`` (``pyjinhx/assets.py``). The
required paths are the union of two sources: the candidates' frozen class
descriptors, which is the only place a clean candidate's assets appear because
a clean candidate never renders, and the session's accumulator, which is the
only place a descendant rendered inside the walk appears because no candidate
names it.
"""

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from pyjinhx.assets import AssetMode, _sorted_resolved, _split_by_origin, asset_token
from pyjinhx.reactive.fanout import FanoutCandidate
from pyjinhx.session import RenderSession

# TODO: cold renders — emit_assets() does not stamp data-pjx-asset yet, so a
# freshly loaded page reports an empty token set and pays one redundant
# re-delivery on its first reactive response.


def required_asset_paths(
    candidates: Iterable[FanoutCandidate],
) -> tuple[set[Path], set[Path]]:
    """The CSS and JS paths every rendering candidate in this walk needs.

    A ``"missing"`` candidate is skipped: its region is being deleted from the
    client, so there is nothing left for an asset to style or drive. Clean
    candidates are included — a region the client already shows correctly can
    still be a region whose stylesheet never arrived.

    Args:
        candidates: ``walk_manifest()`` output.

    Returns:
        The CSS paths and the JS paths, deduped across candidates.
    """
    css: set[Path] = set()
    js: set[Path] = set()
    for candidate in candidates:
        if candidate.status == "missing":
            continue
        # A class that never went through descriptor resolution contributes
        # nothing rather than taking the whole response down over an asset.
        descriptor: Any = getattr(candidate.component_class, "__pjx_descriptor__", None)
        if descriptor is None:
            continue
        css.update(descriptor.css_paths)
        js.update(descriptor.js_paths)
    return css, js


def _inline_fragments(
    paths: set[Path],
    loaded: frozenset[str],
    open_tag: str,
    close_tag: str,
    origin_attr: str = "",
) -> list[str]:
    """One head-targeted OOB fragment per path the client does not report.

    Path-sorted for the same reason ``emit_assets`` sorts: the store is a set,
    and two identical responses must be byte-identical.

    Args:
        origin_attr: Extra markup inserted right after ``data-pjx-asset``, e.g.
            ``' data-pjx-origin="builtin"'`` — pjx.js reads it to keep builtin
            CSS ahead of app CSS when it relocates a late-arriving style.
    """
    fragments: list[str] = []
    for path in sorted(paths, key=str):
        token = asset_token(path)
        if token in loaded:
            continue
        fragments.append(
            f'{open_tag} data-pjx-asset="{token}"{origin_attr} '
            f'hx-swap-oob="beforeend:head">{path.read_text()}{close_tag}'
        )
    return fragments


def _url_fragments(
    paths: set[Path],
    loaded: frozenset[str],
    resolver: Callable[[Path], str],
    template: str,
    origin_attr: str = "",
) -> list[str]:
    """One head-targeted OOB fragment per unloaded path, pointing at its URL.

    Args:
        paths: The asset paths this walk requires.
        loaded: The tokens the client reports it already has.
        resolver: Maps an asset path to the URL it is served from.
        template: A tag with ``{token}``, ``{url}``, and (for CSS) ``{origin}``
            placeholders.
        origin_attr: Value for ``{origin}`` — see ``_inline_fragments``.

    Returns:
        The fragments, in the same path-sorted order ``_inline_fragments`` uses.
    """
    ordered = sorted(paths, key=str)
    wanted = [path for path in ordered if asset_token(path) not in loaded]
    urls = _sorted_resolved(wanted, resolver)
    return [
        template.format(token=asset_token(path), url=url, origin=origin_attr)
        for path, url in zip(wanted, urls, strict=True)
    ]


def missing_asset_oob(
    candidates: Iterable[FanoutCandidate],
    loaded: frozenset[str],
    session: RenderSession,
    resolver: Callable[[Path], str] | None = None,
) -> str:
    """The OOB fragments delivering assets this walk needs and the client lacks.

    Args:
        candidates: ``walk_manifest()`` output for this request.
        loaded: ``LoadedAssets.parse()`` output — the tokens the browser
            reports. An unreadable header parses to an empty set, which means
            every required asset is delivered rather than none.
        session: The RenderSession whose css_mode/js_mode decide delivery and
            whose css_assets/js_assets carry what the walk actually rendered.
        resolver: Maps an asset path to the URL it is served from, in the shape
            asset_manifest() takes. A LINK-mode kind delivers nothing without
            one.

    Returns:
        CSS fragments then JS fragments, newline-joined, or ``""`` when the
        client already has everything, no candidate declares an asset, or the
        session delivers that kind some other way.
    """
    css_paths, js_paths = required_asset_paths(candidates)
    # Unioned, not replaced: a clean candidate short-circuits before it renders,
    # so on_rendered never fires for it and the accumulator never sees the
    # stylesheet its region may still be missing.
    css_paths |= session.css_assets
    js_paths |= session.js_assets
    fragments: list[str] = []
    # Builtin CSS always emits before app CSS, same reason as emit_assets:
    # both are single-class selectors on the same element that tie at
    # specificity, and this response's document order is what the client
    # preserves when it relocates these fragments into <head>.
    builtin_css, app_css = _split_by_origin(css_paths)
    # Builtin CSS is stamped data-pjx-origin="builtin" so pjx.js can insert a
    # late-arriving one ahead of app CSS already resident in <head>, instead
    # of appendChild-ing it wherever it happens to land in the document.
    builtin_origin = ' data-pjx-origin="builtin"'
    # A resolver-less LINK kind emits nothing rather than raising, unlike
    # emit_assets: a reactive response is a partial update, and taking the whole
    # response down over a missing asset URL would blank a working page.
    if session.css_mode is AssetMode.INLINE:
        fragments += _inline_fragments(
            builtin_css, loaded, "<style", "</style>", origin_attr=builtin_origin
        )
        fragments += _inline_fragments(app_css, loaded, "<style", "</style>")
    elif session.css_mode is AssetMode.LINK and resolver is not None:
        link_template = (
            '<link rel="stylesheet" data-pjx-asset="{token}"{origin} '
            'hx-swap-oob="beforeend:head" href="{url}">'
        )
        fragments += _url_fragments(
            builtin_css, loaded, resolver, link_template, origin_attr=builtin_origin
        )
        fragments += _url_fragments(app_css, loaded, resolver, link_template)
    if session.js_mode is AssetMode.INLINE:
        fragments += _inline_fragments(js_paths, loaded, "<script", "</script>")
    elif session.js_mode is AssetMode.LINK and resolver is not None:
        fragments += _url_fragments(
            js_paths,
            loaded,
            resolver,
            '<script data-pjx-asset="{token}" '
            'hx-swap-oob="beforeend:head" src="{url}"></script>',
        )
    return "\n".join(fragments)

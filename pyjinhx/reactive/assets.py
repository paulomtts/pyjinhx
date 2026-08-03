"""The asset delta: which of a fan-out's assets the client does not have yet.

An OOB region swap carries markup only. A region that is being swapped in for
the first time in this page's life still needs its stylesheet and its script,
and the client tells the server which ones it already has in ``X-PJX-Assets``.
This module answers the difference, as head-targeted OOB fragments pjx.js
relocates on arrival (``pyjinhx/client/pjx.js`` reads ``data-pjx-asset``).

Ported from v0.x's ``render_missing_assets_oob`` (``pyjinhx/assets.py``), with
one deliberate difference: the required paths come from the candidates' frozen
class descriptors rather than from a shared RenderSession's accumulator, since
nothing in v2 subscribes ``accumulate_assets`` onto the fan-out render's
session and that accumulator would therefore always be empty.
"""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pyjinhx.assets import AssetMode, asset_token
from pyjinhx.reactive.fanout import FanoutCandidate
from pyjinhx.session import RenderSession

# TODO(#490 follow-up): LINK mode needs a URL resolver to build <link href>/
# <script src> tags, and ReactiveResponse has no resolver to hand down, so a
# LINK-mode app delivers no swap-in assets today. Same for cold renders:
# emit_assets() does not stamp data-pjx-asset yet, so a freshly loaded page
# reports an empty token set and pays one redundant re-delivery on its first
# reactive response.


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
    paths: set[Path], loaded: frozenset[str], open_tag: str, close_tag: str
) -> list[str]:
    """One head-targeted OOB fragment per path the client does not report.

    Path-sorted for the same reason ``emit_assets`` sorts: the store is a set,
    and two identical responses must be byte-identical.
    """
    fragments: list[str] = []
    for path in sorted(paths, key=str):
        token = asset_token(path)
        if token in loaded:
            continue
        fragments.append(
            f'{open_tag} data-pjx-asset="{token}" hx-swap-oob="beforeend:head">'
            f"{path.read_text()}{close_tag}"
        )
    return fragments


def missing_asset_oob(
    candidates: Iterable[FanoutCandidate],
    loaded: frozenset[str],
    session: RenderSession,
) -> str:
    """The OOB fragments delivering assets this walk needs and the client lacks.

    Args:
        candidates: ``walk_manifest()`` output for this request.
        loaded: ``LoadedAssets.parse()`` output — the tokens the browser
            reports. An unreadable header parses to an empty set, which means
            every required asset is delivered rather than none.
        session: The RenderSession whose css_mode/js_mode decide delivery.

    Returns:
        CSS fragments then JS fragments, newline-joined, or ``""`` when the
        client already has everything, no candidate declares an asset, or the
        session delivers that kind some other way.
    """
    css_paths, js_paths = required_asset_paths(candidates)
    fragments: list[str] = []
    if session.css_mode is AssetMode.INLINE:
        fragments += _inline_fragments(css_paths, loaded, "<style", "</style>")
    if session.js_mode is AssetMode.INLINE:
        fragments += _inline_fragments(js_paths, loaded, "<script", "</script>")
    return "\n".join(fragments)

"""One reactive HTTP body: the primary render output plus the OOB fan-out fragments."""

from typing import Literal

from markupsafe import Markup

from pyjinhx2.client.inject import LoadedAssets, MountedManifest
from pyjinhx2.reactive.assets import missing_asset_oob
from pyjinhx2.reactive.cache import invalidate
from pyjinhx2.reactive.fanout import FanoutCandidate, oob_swaps, walk_manifest
from pyjinhx2.session import RenderSession, current_session, get_dirtied


class ReactiveResponse:
    """The composed body for one reactive request.

    Holds the primary render output and the client's raw mounted manifest, and
    answers the single body that goes on the wire: the primary markup followed by
    one OOB fragment per region this request's dirtied keys invalidated.

    Owns the body, the one htmx header the body itself implies (``HX-Reswap:
    none`` for an OOB-only response), and the htmx redirect headers. Framework
    glue is owned elsewhere, so this object stays usable by all of them.
    """

    def __init__(
        self,
        primary: object = None,
        mounted: object = None,
        redirect: str | None = None,
        redirect_mode: Literal["redirect", "location"] = "redirect",
        assets: object = None,
    ) -> None:
        """Store the inputs; nothing is walked or rendered until ``body`` is read.

        Args:
            primary: This request's already-serialized primary render output, or
                None/empty for a handler that renders nothing directly.
            mounted: The raw ``X-PJX-Mounted`` header value, a pre-parsed entry
                list, a request-like object, or None.
            redirect: The URL this response redirects to, or None for no redirect.
            redirect_mode: ``"redirect"`` for a full browser navigation
                (``HX-Redirect``), ``"location"`` for htmx's client-side ajax
                navigation (``HX-Location``). Ignored when ``redirect`` is None.
            assets: The raw ``X-PJX-Assets`` header value, a pre-parsed token
                list, a request-like object, or None. None falls back to
                ``mounted`` when that is itself a request-like object, so a
                handler passing ``mounted=request`` gets both headers for free;
                anything unreadable means "the client has nothing", and every
                required asset is delivered.

        Raises:
            ValueError: If ``redirect`` is given as an empty string.
        """
        # An empty URL would put a meaningless header on the wire and htmx would
        # navigate to the current page; fail where the mistake was made instead.
        if redirect is not None and not redirect.strip():
            raise ValueError("redirect URL must not be empty")
        self.primary = primary
        self.mounted = mounted
        self.redirect = redirect
        self.redirect_mode: Literal["redirect", "location"] = redirect_mode
        self.assets = assets

    def candidates(self) -> list[FanoutCandidate]:
        """The fan-out candidates this request's dirtied keys make of the manifest.

        Returns:
            ``walk_manifest`` output, in manifest order. Empty when nothing is
            mounted, nothing is dirtied, or the header was unreadable.
        """
        dirtied = get_dirtied()
        # Evict before walking, never after: walk_manifest reads the load cache to
        # decide clean vs dirty, so an entry a dirtied key already stale-ed would
        # otherwise answer "clean" and the client would keep markup this request
        # just invalidated.
        invalidate(dirtied)
        # primary_html is passed so a region the primary body already carries is not
        # also swapped OOB: fan-out runs after the primary serialize, and without
        # this the client would swap that region twice in one response.
        return walk_manifest(
            MountedManifest.parse(self.mounted),
            dirtied,
            session=current_session(),
            primary_html=self.primary,
        )

    def _loaded_assets(self) -> frozenset[str]:
        """The asset tokens the client reports, from whichever input carries them.

        ``mounted`` is only consulted when it is a request-like object: a raw
        manifest string or list holds region entries, and handing those to the
        asset parser would invent tokens out of region ids.
        """
        if self.assets is not None:
            return LoadedAssets.parse(self.assets)
        if isinstance(self.mounted, (str, list)) or self.mounted is None:
            return frozenset()
        return LoadedAssets.parse(self.mounted)

    @property
    def body(self) -> Markup:
        """The whole response body: primary markup, OOB fragments, missing assets.

        Returns:
            The primary markup, then one OOB fragment per surviving candidate,
            then the head-targeted fragments for assets those candidates need
            and the client did not report. Concatenation only — the region
            fragments were already stamped by splicing at recorded offsets, so
            nothing here re-parses either side.
        """
        # One walk, not two: candidates() re-renders every dirty region, so
        # asking it again for the asset leg would double every load() and every
        # render this response pays for.
        candidates = self.candidates()
        session = current_session() or RenderSession()
        # Markup(self.primary or "") first, not str(self.primary or ""): a
        # handler-supplied primary can be an object exposing only __html__
        # (never __str__), and Markup() is what adopts that protocol without
        # escaping. str()-ing the raw object first would silently fall through
        # to object.__str__ and ship a Python repr instead of the markup
        # (caught by test_primary_with_dunder_html_is_used_as_markup).
        parts = [
            str(Markup(self.primary or "")),
            str(oob_swaps(candidates)),
            missing_asset_oob(candidates, self._loaded_assets(), session),
        ]
        return Markup("\n".join(part for part in parts if part))

    @property
    def headers(self) -> dict[str, str]:
        """The htmx response headers this body needs.

        Returns:
            ``{"HX-Reswap": "none"}`` when there is no primary markup, else ``{}``,
            plus ``{"HX-Redirect": url}`` or ``{"HX-Location": url}`` when this
            response carries a redirect.
        """
        headers: dict[str, str] = {}
        # An OOB-only body has nothing for htmx's default swap to place, so htmx would
        # swap the empty primary into the triggering element and wipe it. Telling htmx
        # not to swap at all leaves the trigger alone and lets the OOB fragments land.
        if not str(self.primary or "").strip():
            headers["HX-Reswap"] = "none"
        if self.redirect is not None:
            name = "HX-Redirect" if self.redirect_mode == "redirect" else "HX-Location"
            headers[name] = self.redirect
        return headers

    def __html__(self) -> Markup:
        """Return the composed body, so templates interpolate it without escaping."""
        return self.body

    def __str__(self) -> str:
        """Return the composed body as a plain string."""
        return str(self.body)

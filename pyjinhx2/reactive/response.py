"""One reactive HTTP body: the primary render output plus the OOB fan-out fragments."""

from markupsafe import Markup

from pyjinhx2.client.inject import MountedManifest
from pyjinhx2.reactive.fanout import FanoutCandidate, oob_swaps, walk_manifest
from pyjinhx2.session import current_session, get_dirtied


class ReactiveResponse:
    """The composed body for one reactive request.

    Holds the primary render output and the client's raw mounted manifest, and
    answers the single body that goes on the wire: the primary markup followed by
    one OOB fragment per region this request's dirtied keys invalidated.

    Owns the body and the one htmx header the body itself implies (``HX-Reswap:
    none`` for an OOB-only response). htmx redirect adaptation and framework glue
    are owned elsewhere, so this object stays usable by all of them.
    """

    def __init__(self, primary: object = None, mounted: object = None) -> None:
        """Store the two inputs; nothing is walked or rendered until ``body`` is read.

        Args:
            primary: This request's already-serialized primary render output, or
                None/empty for a handler that renders nothing directly.
            mounted: The raw ``X-PJX-Mounted`` header value, a pre-parsed entry
                list, a request-like object, or None.
        """
        self.primary = primary
        self.mounted = mounted

    def candidates(self) -> list[FanoutCandidate]:
        """The fan-out candidates this request's dirtied keys make of the manifest.

        Returns:
            ``walk_manifest`` output, in manifest order. Empty when nothing is
            mounted, nothing is dirtied, or the header was unreadable.
        """
        # primary_html is passed so a region the primary body already carries is not
        # also swapped OOB: fan-out runs after the primary serialize, and without
        # this the client would swap that region twice in one response.
        return walk_manifest(
            MountedManifest.parse(self.mounted),
            get_dirtied(),
            session=current_session(),
            primary_html=self.primary,
        )

    @property
    def body(self) -> Markup:
        """The whole response body: primary markup, then the OOB fragments.

        Returns:
            ``Markup(primary or "") + oob_swaps(candidates)``. Concatenation only —
            the fragments were already stamped by splicing at recorded offsets, so
            nothing here re-parses either side.
        """
        return Markup(self.primary or "") + oob_swaps(self.candidates())

    @property
    def headers(self) -> dict[str, str]:
        """The htmx response headers this body needs.

        Returns:
            ``{"HX-Reswap": "none"}`` when there is no primary markup, else ``{}``.
        """
        # An OOB-only body has nothing for htmx's default swap to place, so htmx would
        # swap the empty primary into the triggering element and wipe it. Telling htmx
        # not to swap at all leaves the trigger alone and lets the OOB fragments land.
        if str(self.primary or "").strip():
            return {}
        return {"HX-Reswap": "none"}

    def __html__(self) -> Markup:
        """Return the composed body, so templates interpolate it without escaping."""
        return self.body

    def __str__(self) -> str:
        """Return the composed body as a plain string."""
        return str(self.body)

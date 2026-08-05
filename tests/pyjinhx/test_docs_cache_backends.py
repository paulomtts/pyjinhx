"""Doc-lint: the tier-2 cache page must match the code it describes.

``docs/api/cache-backends.md`` documents a seam with no public API surface —
``CacheBackend``, ``CachePolicy``, ``DiskCacheBackend`` and the render cache are
all absent from ``pyjinhx.__all__`` — so nothing else in the suite notices when
the page drifts from ``pyjinhx/reactive/backend.py`` or
``pyjinhx/integrations/diskcache.py``. These tests pin the load-bearing claims:
the default ttl, the reserved diskcache key prefix, the protocol's four methods,
and the one sentence on the tier-1 page that this page makes conditional.
"""

import inspect
from pathlib import Path

from pyjinhx.reactive.backend import CacheBackend, CachePolicy

_ROOT = Path(__file__).resolve().parents[2]
_DOCS = _ROOT / "docs"
_PAGE = _DOCS / "api" / "cache-backends.md"
_TIER1_PAGE = _DOCS / "api" / "cache-invalidation.md"


def test_page_is_in_the_internals_nav_after_cache_invalidation():
    nav = (_ROOT / "mkdocs.yml").read_text()

    assert "api/cache-backends.md" in nav, (
        "docs/api/cache-backends.md is not in mkdocs.yml nav; an unlisted page "
        "fails `mkdocs build --strict`"
    )
    tier1 = nav.index("api/cache-invalidation.md")
    tier2 = nav.index("api/cache-backends.md")
    assert tier2 > tier1, (
        "the tier-2 page must follow Cache & Invalidation in the Internals nav"
    )


def test_page_carries_the_internal_module_warning():
    text = _PAGE.read_text()

    assert '!!! warning "Internal module"' in text, (
        "tier 2 is no more public API than tier 1; the page needs the same "
        "internal-module admonition api/cache-invalidation.md carries"
    )


def test_page_documents_every_backend_protocol_method():
    text = _PAGE.read_text()

    # backend.py has `from __future__ import annotations`, so a bare
    # inspect.signature() on these Protocol methods renders every annotation as
    # a quoted string ("key: 'str'") rather than the type itself — eval_str=True
    # resolves them back to real objects, at the cost of fully qualifying
    # collections.abc names, which the stripped-out prefix below undoes to
    # match how the page (reasonably) spells `Iterable[str]` bare.
    for method in ("get", "put", "evict", "clear"):
        sig = inspect.signature(getattr(CacheBackend, method), eval_str=True)
        signature = f"def {method}{sig}".replace("collections.abc.", "")
        assert signature in text, (
            f"api/cache-backends.md's CacheBackend.{method} signature is stale; "
            f"source says: {signature}"
        )


def test_page_states_the_real_default_ttl():
    text = _PAGE.read_text()

    assert f"ttl={CachePolicy().ttl:g}" in text or f"`{CachePolicy().ttl:g}`" in text, (
        f"the page must quote CachePolicy's real default ttl "
        f"({CachePolicy().ttl}); a wrong number here is the whole safety story"
    )
    assert "ttl=None" in text, (
        "the page must say ttl=None is spelled explicitly, never a default"
    )


def test_page_covers_the_diskcache_boundaries():
    text = _PAGE.read_text()

    for claim in ("FanoutCache", "pjx:diskcache:", "NFS", "cache=False"):
        assert claim in text, f"api/cache-backends.md never mentions {claim}"


def test_page_states_what_tier_2_does_not_solve():
    text = _PAGE.read_text()

    assert "## What this does not solve" in text, (
        "the page must state the load()-still-runs-on-every-miss boundary "
        "under its own heading, not bury it in a paragraph"
    )


def test_tier1_page_no_longer_claims_an_unconditional_no_fan_out():
    text = _TIER1_PAGE.read_text()

    assert "there is currently no built-in mechanism" not in text, (
        "DiskCacheBackend.evict() does fan out across workers sharing a "
        "directory; the unconditional claim on api/cache-invalidation.md is "
        "now false and must be scoped to the no-backend case"
    )
    assert "cache-backends.md" in text, (
        "the tier-1 page must cross-link the tier-2 page where it scopes the "
        "fan-out claim, or a reader meets two contradictory statements"
    )

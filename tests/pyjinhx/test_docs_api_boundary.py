"""Doc-lint: the Public API pages must not document Internals symbols.

``docs/api/registry.md`` sits under "API Reference > Public API" in
``mkdocs.yml`` and once covered two unrelated mechanisms: the process-wide
class registry (``pyjinhx.discovery``, internal) and the request-scoped
instance registry (public). Documenting the class registry there put internal
free functions in front of readers being told the top-level ``__all__`` is the
whole public surface. These tests pin the split so it cannot silently regress
the next time either page is edited.
"""

import inspect
from pathlib import Path

import pyjinhx.discovery as discovery

_ROOT = Path(__file__).resolve().parents[2]
_DOCS = _ROOT / "docs"

# Free functions of pyjinhx.discovery. They belong on the Internals page
# (api/finder.md), never on the Public API page (api/registry.md).
CLASS_REGISTRY_SYMBOLS = (
    "build_registry",
    "get_class",
    "register_class",
    "get_template_dir",
)

# Public instance-registry surface that api/registry.md must keep covering.
INSTANCE_REGISTRY_SYMBOLS = (
    "make_key",
    "resolve",
    "register_instance",
    "request_scope",
)


def test_registry_page_documents_only_instance_registry():
    text = (_DOCS / "api" / "registry.md").read_text()

    for symbol in CLASS_REGISTRY_SYMBOLS:
        assert symbol not in text, (
            f"{symbol}() is a pyjinhx.discovery internal; it belongs in "
            f"docs/api/finder.md, not the Public API registry page"
        )

    for symbol in INSTANCE_REGISTRY_SYMBOLS:
        assert symbol in text, f"api/registry.md stopped documenting {symbol}()"


def test_finder_page_documents_register_class():
    text = (_DOCS / "api" / "finder.md").read_text()

    assert "## register_class" in text, (
        "register_class() moved off api/registry.md and must land on the "
        "Internals discovery page"
    )

    signature = f"def register_class{inspect.signature(discovery.register_class)}"
    assert signature in text, (
        f"api/finder.md's register_class signature is stale; source says: {signature}"
    )


def test_mutations_page_has_no_client_backend_claim():
    text = (_DOCS / "api" / "mutations-keys-context.md").read_text()

    assert "ClientBackend" not in text, (
        "enable_reactive_dev() has no backend-presence guardrail — pyjinhx.dev "
        "only implements warn_unconsumed_mutations(); the claim is stale"
    )

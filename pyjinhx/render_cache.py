"""How a rendered level is keyed for the tier-2 (non-reactive) render cache.

Stateless by construction: one pure function over a component instance and the
template file its class resolved to. Storing and restoring entries under this
key lives elsewhere.
"""

import hashlib
import json

from pyjinhx._component import BaseComponent


def render_cache_key(component: BaseComponent) -> str:
    """Return the render-cache key for ``component``.

    Three parts joined by ``:`` — the fully qualified class name, a SHA-256
    digest of the instance's own field values, and the modification time of
    the template the class resolved to.
    """
    cls = type(component)
    descriptor = cls.__pjx_descriptor__
    identity = f"{cls.__module__}.{cls.__qualname__}"
    # JSON-mode dump plus sorted, separator-pinned encoding so dict ordering
    # and non-JSON-native types can't perturb an unchanged set of props.
    canonical = json.dumps(
        component.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    fields_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    # Left to raise: a key that silently drops the template part would serve a
    # stale level forever after an author edits that template, and no restart
    # would clear it.
    template_mtime = descriptor.template_path.stat().st_mtime
    return f"{identity}:{fields_digest}:{template_mtime}"

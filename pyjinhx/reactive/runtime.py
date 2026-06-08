from __future__ import annotations

from markupsafe import Markup

from pyjinhx.core.assets import DEFAULT_RUNTIME_URL, AssetMode
from pyjinhx.core.renderer import Renderer
from pyjinhx.utils import read_client_runtime


def client_script(
    *,
    mode: AssetMode | None = None,
    src: str | None = None,
) -> Markup:
    """
    Return the pyjinhx client runtime as a ``<script>`` tag.

    Drop this into a raw Jinja page shell when you are not rendering through a
    root ``BaseComponent.render()`` call. Root full-page renders inject the
    runtime automatically unless the request already carries ``X-PJX-Mounted``.

    Args:
        mode: ``AssetMode.INLINE`` (default) inlines the runtime source.
            ``AssetMode.REFERENCE`` emits ``<script src="...">``.
        src: Public URL for the runtime when ``mode`` is ``AssetMode.REFERENCE``.
            Defaults to ``Renderer``'s configured runtime URL.
    """
    effective_mode = mode or AssetMode.INLINE
    if effective_mode == AssetMode.REFERENCE:
        runtime_url = src or Renderer._default_runtime_url or DEFAULT_RUNTIME_URL
        return Markup(f'<script src="{runtime_url}"></script>')
    return Markup(f"<script>{read_client_runtime()}</script>")

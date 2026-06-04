from __future__ import annotations

import logging

from markupsafe import Markup

from .utils import read_client_runtime

logger = logging.getLogger("pyjinhx")

PJX_MOUNTED_HEADER = "X-PJX-Mounted"
"""Name of the HTTP header carrying the client's mounted-region manifest."""


def client_script() -> Markup:
    """
    Return the pyjinhx client runtime wrapped in a ``<script>`` tag.

    Drop this into a page shell (e.g. a raw Jinja layout) to emit the
    ``X-PJX-Mounted`` manifest header on every htmx request. When the page shell
    subclasses ``Layout`` the runtime is injected automatically and you do not
    need to call this.
    """
    return Markup(f"<script>{read_client_runtime()}</script>")

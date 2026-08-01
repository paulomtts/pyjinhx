"""One-off generator for pyjinhx2/client/htmx.min.js.

Downloads the pinned htmx release and writes it next to pjx.js so the v2 client
tier can ship htmx itself. Not imported by the package; run manually:

    uv run python scripts/vendor_htmx2.py

The version is pinned rather than tracking latest: L3's wire protocol is coupled
to htmx 2.x's event model, and htmx 4.0 is a beta fetch()-based rewrite (ADR 0012).

htmx is distributed under the 0BSD license.
"""

import urllib.request
from pathlib import Path

HTMX_VERSION = "2.0.3"
URL = f"https://unpkg.com/htmx.org@{HTMX_VERSION}/dist/htmx.min.js"

HEADER = f"/* htmx {HTMX_VERSION} — vendored by scripts/vendor_htmx2.py (0BSD) */\n"


def main() -> None:
    with urllib.request.urlopen(URL, timeout=30) as resp:
        source = resp.read().decode("utf-8")
    out = Path(__file__).resolve().parents[1] / "pyjinhx2/client/htmx.min.js"
    out.write_text(HEADER + source, encoding="utf-8")
    print(f"wrote htmx {HTMX_VERSION} ({len(source)} bytes) to {out}")


if __name__ == "__main__":
    main()

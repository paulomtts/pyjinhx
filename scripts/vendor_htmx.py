"""One-off generator for pyjinhx/runtime/htmx.min.js.

Downloads the pinned htmx release and writes it next to pjx.js so the client
runtime can ship htmx itself (auto-injected before pjx.js on reactive root
renders). Not imported by the package; run manually:

    uv run python scripts/vendor_htmx.py

htmx is distributed under the 0BSD license.
"""
import urllib.request
from pathlib import Path

HTMX_VERSION = "2.0.3"
URL = f"https://unpkg.com/htmx.org@{HTMX_VERSION}/dist/htmx.min.js"

HEADER = f"/* htmx {HTMX_VERSION} — vendored by scripts/vendor_htmx.py (0BSD) */\n"


def main() -> None:
    with urllib.request.urlopen(URL, timeout=30) as resp:
        source = resp.read().decode("utf-8")
    out = Path(__file__).resolve().parents[1] / "pyjinhx/runtime/htmx.min.js"
    out.write_text(HEADER + source, encoding="utf-8")
    print(f"wrote htmx {HTMX_VERSION} ({len(source)} bytes) to {out}")


if __name__ == "__main__":
    main()

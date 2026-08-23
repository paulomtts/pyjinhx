"""One-off generator for pyjinhx/builtins/ui/pjx_icon/_icons.py.

Downloads every Lucide icon at a pinned release and writes their inner SVG
markup into _icons.py. Not imported by the package; run manually:

    uv run python scripts/vendor_lucide_icons.py
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

LUCIDE_TAG = "0.544.0"
RAW = "https://raw.githubusercontent.com/lucide-icons/lucide/{tag}/icons/{name}.svg"
# Non-recursive contents call would need one request per subdirectory and hit
# GitHub's ~1000-entries-per-page cap; the recursive git-tree call returns the
# whole repo listing (icons/ has no subdirectories) in a single request.
TREE_API = (
    "https://api.github.com/repos/lucide-icons/lucide/git/trees/{tag}?recursive=1"
)

INNER_RE = re.compile(r"<svg[^>]*>(.*)</svg>", re.DOTALL)


def list_icon_names() -> list[str]:
    url = TREE_API.format(tag=LUCIDE_TAG)
    with urllib.request.urlopen(url, timeout=30) as resp:
        tree = json.load(resp)["tree"]
    names = [
        entry["path"].removeprefix("icons/").removesuffix(".svg")
        for entry in tree
        if entry["path"].startswith("icons/") and entry["path"].endswith(".svg")
    ]
    return sorted(names)


def fetch_inner(name: str) -> str:
    url = RAW.format(tag=LUCIDE_TAG, name=name)
    with urllib.request.urlopen(url, timeout=30) as resp:
        svg = resp.read().decode("utf-8")
    match = INNER_RE.search(svg)
    if not match:
        raise SystemExit(f"could not parse inner SVG for {name!r}")
    return " ".join(match.group(1).split())


def main() -> None:
    icons: dict[str, str] = {}
    for name in list_icon_names():
        try:
            icons[name] = fetch_inner(name)
        except Exception as exc:  # noqa: BLE001
            print(f"WARN skipping {name}: {exc}", file=sys.stderr)
    out = Path(__file__).resolve().parents[1] / "pyjinhx/builtins/ui/pjx_icon/_icons.py"
    lines = [
        '"""Vendored Lucide icon inner-SVG markup, keyed by name.',
        "",
        "Each value is the *inner* markup of a 24x24 Lucide icon (the children of",
        "the <svg> element), not a full <svg> wrapper. Regenerate/extend with",
        "scripts/vendor_lucide_icons.py. Icons: Lucide (ISC) — see LICENSE.lucide.",
        '"""',
        "",
        "ICONS: dict[str, str] = {",
    ]
    for name, inner in icons.items():
        lines.append(f"    {name!r}: {inner!r},")
    lines.append("}")
    lines.append("")
    lines.append("ICON_NAMES: tuple[str, ...] = tuple(ICONS)")
    lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {len(icons)} icons to {out}")


if __name__ == "__main__":
    main()

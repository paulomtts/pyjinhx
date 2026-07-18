"""One-off generator for pyjinhx/builtins/ui/pjx_icon/_icons.py.

Downloads the curated Lucide icons at a pinned release and writes their inner
SVG markup into _icons.py. Not imported by the package; run manually:

    uv run python scripts/vendor_lucide_icons.py
"""
import re
import sys
import urllib.request
from pathlib import Path

LUCIDE_TAG = "0.544.0"
RAW = "https://raw.githubusercontent.com/lucide-icons/lucide/{tag}/icons/{name}.svg"

CURATED: tuple[str, ...] = (
    # chevrons / arrows / navigation
    "chevron-right", "chevron-left", "chevron-up", "chevron-down",
    "chevrons-left", "chevrons-right", "chevrons-up-down",
    "arrow-right", "arrow-left", "arrow-up", "arrow-down", "arrow-up-right",
    "corner-down-right", "menu",
    "panel-left", "panel-right", "sidebar", "external-link",
    "maximize", "minimize", "expand",
    # actions / editing
    "plus", "plus-circle", "minus", "minus-circle", "x", "check", "edit",
    "pencil", "trash", "trash-2", "copy", "clipboard", "scissors", "save",
    "download", "upload", "share", "share-2", "link", "unlink", "refresh-cw",
    "rotate-cw", "undo", "redo", "send", "filter", "sliders-horizontal",
    "search", "settings", "settings-2",
    # status / feedback
    "triangle-alert", "alert-circle", "info", "check-circle", "x-circle",
    "help-circle", "ban", "shield", "shield-check", "loader", "clock",
    # users / communication
    "user", "users", "user-plus", "user-check", "user-x", "mail", "at-sign",
    "message-square", "message-circle", "phone", "bell", "bell-off",
    # files / data / layout
    "file", "file-text", "files", "folder", "folder-open", "image",
    "paperclip", "archive", "database", "server", "hard-drive",
    "layout-dashboard", "layout-grid", "list", "table", "columns", "calendar",
    # media
    "play", "pause", "square", "skip-forward", "skip-back", "volume-2",
    "volume-x", "mic", "mic-off", "camera",
    # commerce / objects
    "shopping-cart", "credit-card", "dollar-sign", "tag", "gift", "package",
    "truck", "star", "heart", "bookmark", "flag", "thumbs-up", "thumbs-down",
    # visibility / security
    "eye", "eye-off", "lock", "unlock", "key",
    # misc
    "home", "globe", "map-pin", "sun", "moon", "cloud", "zap", "activity",
    "bar-chart", "trending-up", "code", "terminal", "git-branch",
    "log-in", "log-out", "power",
    # issue-99: new additions
    "building", "brain",
    # issue-204: pin/unpin toggle
    "pin", "pin-off",
    # issue-200: overflow/kebab menu trigger
    "ellipsis", "ellipsis-vertical",
)

INNER_RE = re.compile(r"<svg[^>]*>(.*)</svg>", re.DOTALL)


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
    for name in CURATED:
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

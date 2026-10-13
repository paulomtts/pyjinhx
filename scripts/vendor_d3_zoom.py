"""One-off generator for pyjinhx/builtins/ui/pjx_graph/src/d3.vendor.js.

Bundles the pinned d3 subset the graph engine needs (selection + zoom and their
dependencies) into one minified IIFE bound to a private ``__pjxD3`` name, so no
``d3`` ever lands on ``window``. Not imported by the package; needs Node.js/npm
and network access, and is run manually:

    uv run python scripts/vendor_d3_zoom.py

Every package is pinned to an exact version, transitive dependencies included,
so npm cannot float any of them and reruns produce a byte-identical file.

The d3 modules are distributed under the ISC license (d3-ease also carries
Robert Penner's BSD license); their texts are copied into the file header.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

D3_PACKAGES = {
    "d3-selection": "3.0.0",
    "d3-zoom": "3.0.0",
    "d3-dispatch": "3.0.1",
    "d3-drag": "3.0.0",
    "d3-interpolate": "3.0.1",
    "d3-color": "3.1.0",
    "d3-transition": "3.0.1",
    "d3-timer": "3.0.1",
    "d3-ease": "3.0.1",
}
ESBUILD_VERSION = "0.25.0"
MAX_BODY_BYTES = 61_440  # 60 KiB, the graph design's size target

ENTRY = (
    'export { select, pointer } from "d3-selection";\n'
    'export { zoom, zoomIdentity, zoomTransform } from "d3-zoom";\n'
)

HEADER = (
    f"/* d3-selection {D3_PACKAGES['d3-selection']} + d3-zoom {D3_PACKAGES['d3-zoom']}"
    " — vendored by scripts/vendor_d3_zoom.py (ISC) */\n"
)

OUT = (
    Path(__file__).resolve().parents[1]
    / "pyjinhx/builtins/ui/pjx_graph/src/d3.vendor.js"
)


def _run(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.exit(f"{cmd[0]} failed:\n{result.stderr.strip()}")
    return result.stdout


def _licence_block(node_modules: Path) -> str:
    texts: list[str] = []
    for name in D3_PACKAGES:
        text = (node_modules / name / "LICENSE").read_text(encoding="utf-8").strip()
        if text not in texts:
            texts.append(text)
    packages = "\n".join(f"{name} {version}" for name, version in D3_PACKAGES.items())
    block = packages + "\n\n" + "\n\n".join(texts)
    # The texts go inside a block comment, so one containing */ would end it early.
    if "*/" in block:
        sys.exit("a licence text contains '*/' and cannot be embedded in a comment")
    return f"/*\n{block}\n*/\n"


def main() -> None:
    npm = shutil.which("npm")
    if npm is None:
        sys.exit(
            "npm not found on PATH: install Node.js (which ships npm) to vendor d3"
        )
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        package = {
            "private": True,
            "dependencies": {**D3_PACKAGES, "esbuild": ESBUILD_VERSION},
        }
        (work / "package.json").write_text(
            json.dumps(package, indent=2), encoding="utf-8"
        )
        (work / "entry.js").write_text(ENTRY, encoding="utf-8")
        _run([npm, "install", "--no-audit", "--no-fund", "--loglevel=error"], work)
        body = _run(
            [
                str(work / "node_modules/.bin/esbuild"),
                "entry.js",
                "--bundle",
                "--minify",
                "--format=iife",
                "--global-name=__pjxD3",
                "--legal-comments=none",
            ],
            work,
        )
        licence = _licence_block(work / "node_modules")
    size = len(body.encode("utf-8"))
    if size > MAX_BODY_BYTES:
        sys.exit(
            f"minified d3 subset is {size} bytes, over the {MAX_BODY_BYTES}-byte (60 KiB) target"
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(HEADER + licence + body, encoding="utf-8", newline="\n")
    print(f"wrote d3 subset ({size} bytes minified) to {OUT}")


if __name__ == "__main__":
    main()

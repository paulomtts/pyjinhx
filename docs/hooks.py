"""MkDocs hooks: render builtin demos into standalone pages and splice them into the docs."""

import os
import re
import shutil
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)

from demos import DEMOS  # noqa: E402

from pyjinhx import BaseComponent, Registry  # noqa: E402
from pyjinhx.utils import pascal_case_to_kebab_case  # noqa: E402

_MARKER = re.compile(r"<!--\s*demo:\s*([A-Za-z]+)\s*-->")

_PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="demo-base.css">
</head>
<body>
{markup}
</body>
</html>
"""

_IFRAME_STYLE = "width:100%;border:1px solid #8884;border-radius:6px"


def _render_one(value):
    if isinstance(value, BaseComponent):
        return str(value.render())
    return str(value)


def demo_markup(value):
    if isinstance(value, (list, tuple)):
        inner = "\n".join(_render_one(item) for item in value)
        return f'<div class="pjx-demo-stage pjx-demo-stage--row">{inner}</div>'
    return f'<div class="pjx-demo-stage">{_render_one(value)}</div>'


def on_page_markdown(markdown, *, page, config, files):
    def replace(match):
        name = match.group(1)
        if name not in DEMOS:
            raise ValueError(f"unknown demo {name!r} in {page.file.src_path}")
        _factory, height = DEMOS[name]
        prefix = "../" * page.url.count("/")
        return (
            f'<iframe src="{prefix}demos/{pascal_case_to_kebab_case(name)}.html" height="{height}" '
            f'style="{_IFRAME_STYLE}" loading="lazy" title="{name} demo"></iframe>'
        )

    return _MARKER.sub(replace, markdown)


def on_post_build(config):
    out = os.path.join(config["site_dir"], "demos")
    os.makedirs(out, exist_ok=True)
    shutil.copy(os.path.join(HERE, "demos", "base.css"), os.path.join(out, "demo-base.css"))
    for name, (factory, _height) in DEMOS.items():
        path = os.path.join(out, f"{pascal_case_to_kebab_case(name)}.html")
        with open(path, "w", encoding="utf-8") as fh, Registry.request_scope():
            fh.write(_PAGE.format(markup=demo_markup(factory())))

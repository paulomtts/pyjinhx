"""MkDocs hooks: render builtin demos into standalone pages and splice them into the docs."""

import os
import re
import shutil
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)

from demos import DEMOS

from pyjinhx.assets import AssetMode, emit_assets
from pyjinhx.component import BaseComponent, _pascal_to_snake
from pyjinhx.session import RenderSession, accumulate_assets, request_scope


def pascal_case_to_kebab_case(name: str) -> str:
    """Used only for demo output filenames (e.g. ``PJXButton`` -> ``pjx-button``)."""
    return _pascal_to_snake(name).replace("_", "-")


_MARKER = re.compile(r"<!--\s*demo:\s*([A-Za-z]+)\s*-->")

_PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="demo-base.css">
{assets}
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
    shutil.copy(
        os.path.join(HERE, "demos", "base.css"), os.path.join(out, "demo-base.css")
    )
    for name, (factory, _height) in DEMOS.items():
        path = os.path.join(out, f"{pascal_case_to_kebab_case(name)}.html")
        # Build and hook the session before request_scope() binds it: demo
        # factories call component.render() with no argument, which renders
        # against whatever current_session() returns, so accumulate_assets
        # must already be subscribed by then.
        session = RenderSession(template_dir="/")
        session.on_rendered.append(accumulate_assets)
        # BaseComponent.render() (what every factory calls, with no argument)
        # is the top-level rendering.render() API, which always appends its
        # own emit_assets(session) call to whatever it returns. A demo whose
        # factory renders N components against this one shared session would
        # otherwise bake N (growing, duplicate) copies of the same assets
        # into markup itself. NONE suppresses that per-call self-emission —
        # accumulate_assets still fires and fills css_assets/js_assets either
        # way, since it is wired to on_rendered, not gated by these modes —
        # so the sets are complete once factory() returns and css_mode/js_mode
        # flip back to INLINE for the single, real emit_assets call below.
        session.css_mode = AssetMode.NONE
        session.js_mode = AssetMode.NONE
        with request_scope(template_dir="/", session=session):
            markup = demo_markup(factory())
        # No inject_runtime: these pages are static snapshots in an iframe
        # and no demo needs htmx/pjx.js to paint. LINK mode is never used, so
        # emit_assets needs no resolver.
        session.css_mode = AssetMode.INLINE
        session.js_mode = AssetMode.INLINE
        assets = emit_assets(session)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_PAGE.format(markup=markup, assets=assets))

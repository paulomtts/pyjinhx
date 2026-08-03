"""L2.2.2: INLINE/NONE emission of accumulated assets at the top-level serialize."""

from pathlib import Path

from pyjinhx.assets import AssetMode
from pyjinhx.session import RenderSession


def test_asset_mode_members_are_inline_none_and_link():
    assert AssetMode.INLINE.value == "inline"
    assert AssetMode.NONE.value == "none"
    assert AssetMode.LINK.value == "link"
    assert set(AssetMode) == {AssetMode.INLINE, AssetMode.NONE, AssetMode.LINK}


def test_session_defaults_both_kinds_to_inline():
    session = RenderSession(template_dir=str(Path("tests/templates")))
    assert session.css_mode is AssetMode.INLINE
    assert session.js_mode is AssetMode.INLINE


import pytest

from pyjinhx.assets import emit_assets


def _session(tmp_path: Path) -> RenderSession:
    return RenderSession(template_dir=str(tmp_path))


def test_inline_emits_style_and_script_with_exact_file_contents(tmp_path):
    css = tmp_path / "box.css"
    css.write_text(".box { color: red; }")
    js = tmp_path / "box.js"
    js.write_text("console.log('box');")
    session = _session(tmp_path)
    session.css_assets.add(css)
    session.js_assets.add(js)

    out = emit_assets(session)

    assert "<style>.box { color: red; }</style>" in out
    assert "<script>console.log('box');</script>" in out


def test_none_mode_emits_nothing_for_that_kind(tmp_path):
    css = tmp_path / "box.css"
    css.write_text(".box { color: red; }")
    js = tmp_path / "box.js"
    js.write_text("console.log('box');")
    session = _session(tmp_path)
    session.css_assets.add(css)
    session.js_assets.add(js)
    session.css_mode = AssetMode.NONE
    session.js_mode = AssetMode.NONE

    assert emit_assets(session) == ""


def test_mixed_modes_emit_css_only(tmp_path):
    css = tmp_path / "box.css"
    css.write_text(".box { color: red; }")
    js = tmp_path / "box.js"
    js.write_text("console.log('box');")
    session = _session(tmp_path)
    session.css_assets.add(css)
    session.js_assets.add(js)
    session.js_mode = AssetMode.NONE

    out = emit_assets(session)

    assert "<style>" in out
    assert "<script>" not in out


def test_emission_order_is_sorted_by_path_and_stable(tmp_path):
    for name, body in (("z.css", ".z {}"), ("a.css", ".a {}"), ("m.css", ".m {}")):
        (tmp_path / name).write_text(body)
    session = _session(tmp_path)
    session.css_assets.update(
        {tmp_path / "z.css", tmp_path / "a.css", tmp_path / "m.css"}
    )

    first = emit_assets(session)

    assert first.index(".a {}") < first.index(".m {}") < first.index(".z {}")
    assert emit_assets(session) == first


def test_missing_asset_file_raises(tmp_path):
    session = _session(tmp_path)
    session.css_assets.add(tmp_path / "gone.css")

    with pytest.raises(OSError):
        emit_assets(session)


def test_no_assets_emits_empty_string(tmp_path):
    assert emit_assets(_session(tmp_path)) == ""


def _stub_resolver(path: Path) -> str:
    """Resolver of the shape #552 will thread in: path -> served URL."""
    return f"/static/{path.name}"


def test_link_mode_emits_stylesheet_links_sorted_by_path(tmp_path):
    session = _session(tmp_path)
    session.css_assets.update(
        {tmp_path / "z.css", tmp_path / "a.css", tmp_path / "m.css"}
    )
    session.css_mode = AssetMode.LINK
    session.js_mode = AssetMode.NONE

    out = emit_assets(session, resolver=_stub_resolver)

    assert out == (
        '<link rel="stylesheet" href="/static/a.css">\n'
        '<link rel="stylesheet" href="/static/m.css">\n'
        '<link rel="stylesheet" href="/static/z.css">'
    )


def test_link_mode_emits_script_src_tags_sorted_by_path(tmp_path):
    session = _session(tmp_path)
    session.js_assets.update({tmp_path / "z.js", tmp_path / "a.js"})
    session.css_mode = AssetMode.NONE
    session.js_mode = AssetMode.LINK

    out = emit_assets(session, resolver=_stub_resolver)

    assert out == (
        '<script src="/static/a.js"></script>\n<script src="/static/z.js"></script>'
    )


def test_resolver_that_raises_propagates_out_of_emit_assets(tmp_path):
    def boom(path: Path) -> str:
        raise FileNotFoundError(path)

    session = _session(tmp_path)
    session.css_assets.add(tmp_path / "gone.css")
    session.css_mode = AssetMode.LINK

    with pytest.raises(FileNotFoundError):
        emit_assets(session, resolver=boom)


def test_link_css_with_inline_js_emits_both_css_first(tmp_path):
    css = tmp_path / "box.css"
    css.write_text(".box { color: red; }")
    js = tmp_path / "box.js"
    js.write_text("console.log('box');")
    session = _session(tmp_path)
    session.css_assets.add(css)
    session.js_assets.add(js)
    session.css_mode = AssetMode.LINK

    out = emit_assets(session, resolver=_stub_resolver)

    assert out == (
        '<link rel="stylesheet" href="/static/box.css">\n'
        "<script>console.log('box');</script>"
    )


from dataclasses import replace

from pyjinhx.component import BaseComponent
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.rendering import render, render_level
from pyjinhx.segments import serialize
from pyjinhx.session import accumulate_assets, request_scope

TEMPLATES = str(Path(__file__).parent.parent / "templates")


def _plain_descriptor(owner: type) -> ClassDescriptor:
    """Hand-built descriptor pointed at the shared plain_div.html fixture."""
    return ClassDescriptor(
        template_path=Path("plain_div.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": owner},
    )


class EmitBox(BaseComponent):
    """Component rendered against a hand-built descriptor, not MRO discovery."""


class EmitSibling(BaseComponent):
    """Second class used to prove a shared asset inlines exactly once."""


EmitBox.__pjx_descriptor__ = _plain_descriptor(EmitBox)
EmitSibling.__pjx_descriptor__ = _plain_descriptor(EmitSibling)


def _with_assets(cls, *, css=(), js=()):
    cls.__pjx_descriptor__ = replace(
        cls.__pjx_descriptor__, css_paths=tuple(css), js_paths=tuple(js)
    )
    return cls


def _accumulating_session() -> RenderSession:
    session = RenderSession(template_dir=TEMPLATES)
    session.on_rendered.append(accumulate_assets)
    return session


def test_render_inlines_accumulated_css_and_js(tmp_path):
    css = tmp_path / "box.css"
    css.write_text(".box { color: red; }")
    js = tmp_path / "box.js"
    js.write_text("console.log('box');")
    _with_assets(EmitBox, css=[css], js=[js])
    session = _accumulating_session()

    out = render(EmitBox(), session)

    assert "<style>.box { color: red; }</style>" in out
    assert "<script>console.log('box');</script>" in out


def test_render_with_none_modes_returns_plain_markup(tmp_path):
    css = tmp_path / "box.css"
    css.write_text(".box { color: red; }")
    _with_assets(EmitBox, css=[css])
    session = _accumulating_session()
    session.css_mode = AssetMode.NONE
    session.js_mode = AssetMode.NONE

    out = render(EmitBox(), session)

    assert "<style>" not in out
    assert "<script>" not in out


def test_shared_asset_inlined_exactly_once(tmp_path):
    css = tmp_path / "shared.css"
    css.write_text(".shared { color: blue; }")
    _with_assets(EmitBox, css=[css])
    _with_assets(EmitSibling, css=[css])
    session = _accumulating_session()

    render(EmitBox(), session)
    out = render(EmitSibling(), session)

    assert out.count(".shared { color: blue; }") == 1


def test_render_without_assets_equals_plain_serialize():
    """With nothing accumulated, render()'s output is exactly serialize(level).
    Reuses one component instance across both calls: auto_id is minted once at
    construction (a process-wide counter), so two separate instances would
    differ by id regardless of asset emission."""
    _with_assets(EmitBox)
    component = EmitBox()

    out = render(component, _accumulating_session())
    expected = serialize(render_level(component, _accumulating_session()))

    assert out == expected


def test_render_level_alone_carries_no_inlined_tags(tmp_path):
    css = tmp_path / "box.css"
    css.write_text(".box { color: red; }")
    _with_assets(EmitBox, css=[css])
    session = _accumulating_session()

    level = render_level(EmitBox(), session)

    assert "<style>" not in serialize(level)
    assert session.css_assets == {css}


import threading


def test_concurrent_scopes_do_not_leak_emitted_assets(tmp_path):
    red = tmp_path / "red.css"
    red.write_text(".red {}")
    blue = tmp_path / "blue.css"
    blue.write_text(".blue {}")
    results: dict[str, str] = {}
    barrier = threading.Barrier(2)

    def run(name: str, asset: Path, mode: AssetMode) -> None:
        session = RenderSession(template_dir=TEMPLATES)
        session.on_rendered.append(accumulate_assets)
        session.css_mode = mode
        with request_scope(session=session):
            session.css_assets.add(asset)
            barrier.wait()
            results[name] = render(EmitSibling(), session)

    _with_assets(EmitSibling)
    threads = [
        threading.Thread(target=run, args=("a", red, AssetMode.INLINE)),
        threading.Thread(target=run, args=("b", blue, AssetMode.NONE)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert ".red {}" in results["a"]
    assert ".blue {}" not in results["a"]
    assert "<style>" not in results["b"]


def test_sorted_resolved_sorts_paths_by_str_before_resolving():
    from pyjinhx.assets import _sorted_resolved

    seen: list[Path] = []

    def resolver(path: Path) -> str:
        seen.append(path)
        return f"/static/{path.name}"

    paths = {Path("/a/z.css"), Path("/a/b.css"), Path("/a/m.css")}

    assert _sorted_resolved(paths, resolver) == (
        "/static/b.css",
        "/static/m.css",
        "/static/z.css",
    )
    assert seen == [Path("/a/b.css"), Path("/a/m.css"), Path("/a/z.css")]


def test_sorted_resolved_lets_a_raising_resolver_propagate():
    from pyjinhx.assets import _sorted_resolved

    def resolver(path: Path) -> str:
        raise OSError("gone")

    with pytest.raises(OSError):
        _sorted_resolved({Path("/a/b.css")}, resolver)


def test_link_mode_without_resolver_raises_value_error(tmp_path):
    session = _session(tmp_path)
    session.css_assets.add(tmp_path / "box.css")
    session.css_mode = AssetMode.LINK

    with pytest.raises(ValueError, match="LINK mode needs a resolver"):
        emit_assets(session)


def test_link_mode_css_and_js_together_sorted_independently_and_css_first(tmp_path):
    session = _session(tmp_path)
    session.css_assets.update({tmp_path / "z.css", tmp_path / "a.css"})
    session.js_assets.update({tmp_path / "z.js", tmp_path / "a.js"})
    session.css_mode = AssetMode.LINK
    session.js_mode = AssetMode.LINK

    out = emit_assets(session, resolver=_stub_resolver)

    assert out == (
        '<link rel="stylesheet" href="/static/a.css">\n'
        '<link rel="stylesheet" href="/static/z.css">\n'
        '<script src="/static/a.js"></script>\n'
        '<script src="/static/z.js"></script>'
    )


def test_link_mode_js_resolver_raise_propagates(tmp_path):
    """A resolver raising on the JS branch is not swallowed by the CSS branch
    having already succeeded."""

    def boom(path: Path) -> str:
        raise FileNotFoundError(path)

    session = _session(tmp_path)
    session.js_assets.add(tmp_path / "gone.js")
    session.css_mode = AssetMode.NONE
    session.js_mode = AssetMode.LINK

    with pytest.raises(FileNotFoundError):
        emit_assets(session, resolver=boom)


def test_link_mode_repeated_calls_are_byte_identical(tmp_path):
    session = _session(tmp_path)
    # Enough members that a set's iteration order would plausibly differ from
    # sorted order, so an unsorted implementation cannot pass by luck.
    session.css_assets.update(
        {tmp_path / name for name in ("z.css", "a.css", "m.css", "b.css", "q.css")}
    )
    session.js_assets.update(
        {tmp_path / name for name in ("z.js", "a.js", "m.js", "b.js", "q.js")}
    )
    session.css_mode = AssetMode.LINK
    session.js_mode = AssetMode.LINK

    first = emit_assets(session, resolver=_stub_resolver)
    second = emit_assets(session, resolver=_stub_resolver)

    assert first == second
    assert first.index("/static/a.css") < first.index("/static/m.css")
    assert first.index("/static/m.css") < first.index("/static/z.css")
    assert first.index("/static/q.css") < first.index("/static/a.js")


def test_emit_assets_puts_runtime_script_before_component_scripts(tmp_path):
    script = tmp_path / "widget.js"
    script.write_text("widget();")
    session = _session(tmp_path)
    session.js_assets = {script}
    session.runtime_script = "<script>RUNTIME</script>"

    html = emit_assets(session)

    assert html.index("RUNTIME") < html.index("widget();")


def test_emit_assets_skips_runtime_script_when_js_mode_is_not_inline(tmp_path):
    session = _session(tmp_path)
    session.js_mode = AssetMode.NONE
    session.runtime_script = "<script>RUNTIME</script>"

    assert emit_assets(session) == ""

import os

import pytest

from pyjinhx import (
    AssetMode,
    BaseComponent,
    Finder,
    Renderer,
    asset_manifest,
    client_script,
    hashed_filename,
    make_default_asset_url_resolver,
    oob_swaps,
    resolver_with_hash,
)
from pyjinhx.utils import read_client_runtime
from tests.ui.reactive.reactive_counter import ReactiveCounter
from tests.ui.unified_component import UnifiedComponent


@pytest.fixture(autouse=True)
def reset_renderer_defaults():
    original_js = Renderer._default_js_mode
    original_css = Renderer._default_css_mode
    original_resolver = Renderer._asset_url_resolver
    original_runtime_url = Renderer._default_runtime_url
    Renderer._default_renderers.clear()
    yield
    Renderer.set_default_js_mode(original_js)
    Renderer.set_default_css_mode(original_css)
    Renderer.set_asset_url_resolver(original_resolver)
    Renderer.set_default_runtime_url(original_runtime_url)
    Renderer._default_renderers.clear()


def test_reference_mode_emits_link_and_script_tags():
    def resolver(path: str) -> str:
        return f"/assets/{os.path.basename(path)}"

    renderer = Renderer.get_default_renderer(
        js_mode=AssetMode.REFERENCE,
        css_mode=AssetMode.REFERENCE,
    )
    Renderer.set_asset_url_resolver(resolver)
    renderer = Renderer.get_default_renderer(
        js_mode=AssetMode.REFERENCE,
        css_mode=AssetMode.REFERENCE,
    )

    rendered = str(UnifiedComponent(id="ref-1", text="Ref")._render(_renderer=renderer))

    assert '<link rel="stylesheet" href="/assets/unified-component.css">' in rendered
    assert '<script src="/assets/unified-component.js"></script>' in rendered
    assert "<style>" not in rendered
    assert "<script>console.log" not in rendered


def test_reference_mode_deduplicates_nested_components():
    renderer = Renderer.get_default_renderer(
        js_mode=AssetMode.REFERENCE,
        css_mode=AssetMode.REFERENCE,
    )
    nested = UnifiedComponent(id="nested", text="Nested")
    component = UnifiedComponent(id="parent", title="Parent", items=[nested])

    rendered = str(component._render(_renderer=renderer))

    assert rendered.count('href="/static/components/') == 1
    assert rendered.count('src="/static/components/') == 1


def test_reference_mode_order_css_before_html_js_after():
    renderer = Renderer.get_default_renderer(
        js_mode=AssetMode.REFERENCE,
        css_mode=AssetMode.REFERENCE,
    )
    rendered = str(
        UnifiedComponent(id="order-1", text="Order")._render(_renderer=renderer)
    )

    link_pos = rendered.find("<link")
    div_pos = rendered.find("<div")
    script_pos = rendered.find("<script")
    assert link_pos < div_pos < script_pos


def test_reference_mode_extra_assets():
    renderer = Renderer.get_default_renderer(
        js_mode=AssetMode.REFERENCE,
        css_mode=AssetMode.REFERENCE,
    )
    component = UnifiedComponent(
        id="extra-ref",
        text="Extra",
        js=["tests/ui/extra_script.js"],
        css=["tests/ui/extra_style.css"],
    )

    rendered = str(component._render(_renderer=renderer))

    assert "extra_style.css" in rendered
    assert "extra_script.js" in rendered


def test_none_mode_stays_silent():
    renderer = Renderer.get_default_renderer(
        js_mode=AssetMode.NONE,
        css_mode=AssetMode.NONE,
    )
    rendered = str(
        UnifiedComponent(id="none-1", text="Silent")._render(_renderer=renderer)
    )

    assert "<style>" not in rendered
    assert "<script" not in rendered
    assert "<link" not in rendered


def test_set_default_js_mode_none():
    Renderer.set_default_js_mode(AssetMode.NONE)
    renderer = Renderer.get_default_renderer()
    assert renderer._js_mode == AssetMode.NONE


def test_asset_manifest_matches_reference_output():
    renderer = Renderer.get_default_renderer(
        js_mode=AssetMode.REFERENCE,
        css_mode=AssetMode.REFERENCE,
    )
    session = renderer.new_session()
    component = UnifiedComponent(id="manifest-1", text="Manifest")
    rendered = str(
        renderer.render_component_with_context(
            component,
            context=component.model_dump(),
            template_source=None,
            template_path=None,
            session=session,
            is_root=True,
            collect_component_js=True,
        )
    )
    resolver = make_default_asset_url_resolver(os.getcwd())
    manifest = asset_manifest(session, resolver=resolver)

    for url in manifest.stylesheets:
        assert url in rendered
    for url in manifest.scripts:
        assert url in rendered


def test_layout_asset_tags_lists_all_files():
    finder = Finder(root="tests/ui")

    def resolver(path: str) -> str:
        return f"/static/{os.path.basename(path)}"

    tags = str(finder.layout_asset_tags(resolver=resolver))

    assert "unified-component.css" in tags
    assert "unified-component.js" in tags
    assert tags.index("<link") < tags.index("<script")


def test_hashed_filename_is_stable():
    path = "tests/ui/unified-component.js"
    first = hashed_filename(path)
    second = hashed_filename(path)
    assert first == second
    assert first.endswith(".js")
    assert "." in first.removesuffix(".js")


def test_resolver_with_hash_embeds_digest():
    resolver = resolver_with_hash("/static/components", "tests/ui")
    url = resolver(os.path.abspath("tests/ui/unified-component.js"))
    assert url.startswith("/static/components/")
    assert url.count(".") >= 2


def test_reactive_partial_render_suppresses_assets():
    from tests.reactive_test_support import reactive_client, record_mutation

    manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
    with reactive_client(manifest):
        record_mutation("todos")
        rendered = str(ReactiveCounter.render())

    assert "<style>" not in rendered
    assert "<script" not in rendered
    assert "<link" not in rendered


def test_oob_swaps_emit_no_assets():
    manifest = [{"id": "counter", "type": "ReactiveCounter", "hash": "stale"}]
    rendered = str(oob_swaps({"todos"}, manifest))

    assert "<style>" not in rendered
    assert "<script" not in rendered
    assert "<link" not in rendered


class Page(BaseComponent):
    pass


@pytest.mark.pjx_runtime
def test_layout_reference_mode_emits_runtime_src():
    renderer = Renderer.get_default_renderer(js_mode=AssetMode.REFERENCE)
    Renderer.set_default_runtime_url("/static/pyjinhx/pjx.js")
    renderer = Renderer.get_default_renderer(js_mode=AssetMode.REFERENCE)

    rendered = str(
        Page(id="page")._render(
            source="<html><body>hi</body></html>", _renderer=renderer
        )
    )

    assert '<script src="/static/pyjinhx/pjx.js"></script>' in rendered
    assert read_client_runtime() not in rendered


def test_client_script_reference_mode():
    Renderer.set_default_runtime_url("/static/pyjinhx/pjx.js")
    script = str(client_script(mode=AssetMode.REFERENCE))

    assert script == '<script src="/static/pyjinhx/pjx.js"></script>'


def test_inline_mode_regression():
    renderer = Renderer.get_default_renderer(
        js_mode=AssetMode.INLINE,
        css_mode=AssetMode.INLINE,
    )
    rendered = str(
        UnifiedComponent(id="inline-1", text="Inline")._render(_renderer=renderer)
    )

    assert "<style>" in rendered
    assert ".test-component { color: red; }" in rendered
    assert "<script>console.log('Button loaded');</script>" in rendered

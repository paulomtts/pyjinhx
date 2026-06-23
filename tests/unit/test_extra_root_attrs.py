from tests.ui.unified_component import UnifiedComponent


def test_render_threads_extra_root_attrs_into_root_tag():
    # emit_assets=False keeps output to just the component HTML (no <style>/<script>
    # injected before/after the root), so index checks target the root opening tag.
    html = str(
        UnifiedComponent(id="w", text="hi")._render(
            emit_assets=False,
            _extra_root_attrs={"hx-swap-oob": "outerHTML:[data-pjx-id='w']"},
        )
    )
    assert html.count("hx-swap-oob=\"outerHTML:[data-pjx-id='w']\"") == 1
    # spliced into the single root opening tag (before its closing '>')
    assert html.index("hx-swap-oob") < html.index(">")

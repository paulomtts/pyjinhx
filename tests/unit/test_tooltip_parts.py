"""Unit tests for PJXTooltipTrigger and PJXTooltipContent composable parts."""

from pyjinhx.assets import AssetMode
from pyjinhx.renderer import Renderer


def _html(component, *, css=False):
    """Render a component with no JS and optionally no CSS."""
    prev_js = Renderer._default_js_mode
    prev_css = Renderer._default_css_mode
    Renderer.set_default_js_mode(AssetMode.NONE)
    if not css:
        Renderer.set_default_css_mode(AssetMode.NONE)
    try:
        return str(component.render())
    finally:
        Renderer.set_default_js_mode(prev_js)
        Renderer.set_default_css_mode(prev_css)


def test_trigger_single_root_span():
    from pyjinhx.builtins import PJXTooltipTrigger
    html = _html(PJXTooltipTrigger(id="tr"))
    assert html.count("<span") == 1
    assert html.count("</span>") == 1


def test_trigger_has_correct_class():
    from pyjinhx.builtins import PJXTooltipTrigger
    html = _html(PJXTooltipTrigger(id="tr"))
    assert 'class="pjx-tooltip__trigger"' in html


def test_trigger_has_id():
    from pyjinhx.builtins import PJXTooltipTrigger
    html = _html(PJXTooltipTrigger(id="my-trigger"))
    assert 'id="my-trigger"' in html


def test_trigger_class_name():
    from pyjinhx.builtins import PJXTooltipTrigger
    html = _html(PJXTooltipTrigger(id="tr", class_name="extra"))
    assert 'class="pjx-tooltip__trigger extra"' in html


def test_trigger_has_tabindex():
    from pyjinhx.builtins import PJXTooltipTrigger
    html = _html(PJXTooltipTrigger(id="tr"))
    assert 'tabindex="0"' in html


def test_trigger_renders_content():
    from pyjinhx.builtins import PJXTooltipTrigger
    html = _html(PJXTooltipTrigger(id="tr", content="Hover me"))
    assert "Hover me" in html


def test_content_single_root_span():
    from pyjinhx.builtins import PJXTooltipContent
    html = _html(PJXTooltipContent(id="tc"))
    assert html.count("<span") == 1
    assert html.count("</span>") == 1


def test_content_has_correct_class():
    from pyjinhx.builtins import PJXTooltipContent
    html = _html(PJXTooltipContent(id="tc"))
    assert 'class="pjx-tooltip__tip"' in html


def test_content_has_id():
    from pyjinhx.builtins import PJXTooltipContent
    html = _html(PJXTooltipContent(id="my-content"))
    assert 'id="my-content"' in html


def test_content_class_name():
    from pyjinhx.builtins import PJXTooltipContent
    html = _html(PJXTooltipContent(id="tc", class_name="extra"))
    assert 'class="pjx-tooltip__tip extra"' in html


def test_content_has_role_tooltip():
    from pyjinhx.builtins import PJXTooltipContent
    html = _html(PJXTooltipContent(id="tc"))
    assert 'role="tooltip"' in html


def test_content_has_hidden():
    from pyjinhx.builtins import PJXTooltipContent
    html = _html(PJXTooltipContent(id="tc"))
    assert "hidden" in html


def test_content_renders_content():
    from pyjinhx.builtins import PJXTooltipContent
    html = _html(PJXTooltipContent(id="tc", content="Helpful text"))
    assert "Helpful text" in html


def test_shell_single_root_span():
    from pyjinhx.builtins import PJXTooltip
    html = _html(PJXTooltip(id="tt"))
    assert html.count("<span") == 1
    assert html.count("</span>") == 1


def test_shell_has_placement_attr():
    from pyjinhx.builtins import PJXTooltip
    html = _html(PJXTooltip(id="tt", placement="bottom"))
    assert 'data-pjx-tooltip-placement="bottom"' in html


def test_shell_no_trigger_tip_fields():
    from pyjinhx.builtins import PJXTooltip
    assert "trigger" not in PJXTooltip.model_fields
    assert "tip" not in PJXTooltip.model_fields


def test_composed_tooltip(tmp_path):
    from pyjinhx import Renderer
    from pyjinhx.builtins import PJXTooltip, PJXTooltipContent, PJXTooltipTrigger  # noqa: F401

    Renderer.set_default_environment(str(tmp_path))
    renderer = Renderer.get_default_renderer()

    rendered = renderer.render(
        '<PJXTooltip id="tt" placement="top">'
        '<PJXTooltipTrigger id="tt-tr">Hover me</PJXTooltipTrigger>'
        '<PJXTooltipContent id="tt-tc">Helpful text</PJXTooltipContent>'
        '</PJXTooltip>'
    )

    assert 'class="pjx-tooltip"' in rendered
    assert 'data-pjx-tooltip-placement="top"' in rendered
    assert 'class="pjx-tooltip__trigger"' in rendered
    assert 'class="pjx-tooltip__tip"' in rendered
    assert "Hover me" in rendered
    assert "Helpful text" in rendered

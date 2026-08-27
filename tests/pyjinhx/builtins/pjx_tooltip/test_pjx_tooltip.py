"""PJXTooltip renders the positioned root shell that anchors a trigger to its tip (port of v0.x pyjinhx/builtins/ui/pjx_tooltip/pjx_tooltip.py)."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_tooltip import PJXTooltip
from pyjinhx.builtins.ui.pjx_tooltip_content import PJXTooltipContent
from pyjinhx.builtins.ui.pjx_tooltip_trigger import PJXTooltipTrigger
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def tooltip_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession()


def _html(session, **kw) -> str:
    return render(PJXTooltip(id="tt", **kw), session)


def test_default_render_is_a_single_top_placed_root(tooltip_session):
    assert _html(tooltip_session) == (
        '<span id="tt" class="pjx-tooltip" data-pjx-tooltip-placement="top"></span>'
    )


def test_root_is_a_single_span(tooltip_session):
    html = _html(tooltip_session, content="x")
    assert html.count("<span") == 1
    assert html.count("</span>") == 1


@pytest.mark.parametrize("placement", ["top", "bottom", "start", "end"])
def test_each_placement_reaches_the_data_attribute(tooltip_session, placement):
    assert f'data-pjx-tooltip-placement="{placement}"' in _html(
        tooltip_session, placement=placement
    )


def test_class_name_appended_to_root(tooltip_session):
    assert 'class="pjx-tooltip extra"' in _html(tooltip_session, class_name="extra")


def test_string_content_is_interpolated(tooltip_session):
    assert ">hello</span>" in _html(tooltip_session, content="hello")


def test_empty_content_renders_an_empty_root(tooltip_session):
    assert _html(tooltip_session).endswith("></span>")


def test_backdrop_is_off_by_default(tooltip_session):
    assert "pjx-tooltip__backdrop" not in _html(tooltip_session, content="hello")


def test_backdrop_renders_a_hidden_overlay_before_the_content(tooltip_session):
    html = _html(tooltip_session, backdrop=True, content="hello")
    assert html == (
        '<span id="tt" class="pjx-tooltip" data-pjx-tooltip-placement="top">'
        '<span class="pjx-tooltip__backdrop" data-pjx-tooltip-backdrop hidden></span>'
        "hello</span>"
    )


def test_backdrop_overlay_joins_the_composed_trigger_and_tip(tooltip_session):
    """The backdrop is a sibling of the trigger and tip, so one root drives all three."""
    html = render(
        PJXTooltip(
            id="tt",
            backdrop=True,
            content=[
                PJXTooltipTrigger(id="tr", content="Hover me"),
                PJXTooltipContent(id="tc", content="Tip text"),
            ],
        ),
        tooltip_session,
    )
    assert html == (
        '<span id="tt" class="pjx-tooltip" data-pjx-tooltip-placement="top">'
        '<span class="pjx-tooltip__backdrop" data-pjx-tooltip-backdrop hidden></span>'
        '<span id="tr" class="pjx-tooltip__trigger" tabindex="0">Hover me</span>'
        '<span id="tc" class="pjx-tooltip__tip" role="tooltip" hidden>Tip text</span>'
        "</span>"
    )


def test_backdrop_rejects_a_non_boolean():
    with pytest.raises(ValidationError):
        PJXTooltip(id="tt", backdrop="yes please")  # type: ignore[arg-type]


def test_portal_is_off_by_default(tooltip_session):
    assert "data-pjx-tooltip-portal" not in _html(tooltip_session)


def test_portal_true_adds_the_data_attribute(tooltip_session):
    html = _html(tooltip_session, portal=True)
    assert 'data-pjx-tooltip-placement="top" data-pjx-tooltip-portal' in html


def test_portal_rejects_a_non_boolean():
    with pytest.raises(ValidationError):
        PJXTooltip(id="tt", portal="yes please")  # type: ignore[arg-type]


def test_invalid_placement_is_rejected():
    with pytest.raises(ValidationError):
        PJXTooltip(id="tt", placement="middle")  # type: ignore[arg-type]


def test_extra_attrs_surface_on_the_root(tooltip_session):
    html = _html(tooltip_session, extra_attrs={"data-testid": "tooltip"})
    assert 'data-testid="tooltip"' in html[: html.index(">")]


def test_assets_are_discovered_from_the_component_directory():
    """CSS and JS sit next to the module and are picked up by the descriptor, with no manual wiring."""
    descriptor = PJXTooltip.__pjx_descriptor__
    assert any(p.name == "pjx_tooltip.js" for p in descriptor.js_paths)
    assert any(p.name == "pjx_tooltip.css" for p in descriptor.css_paths)


def test_composed_tooltip_nests_trigger_and_tip_under_one_root(tooltip_session):
    """The shape the positioning JS walks: one root, a focusable trigger, a hidden tip."""
    html = render(
        PJXTooltip(
            id="tt",
            placement="bottom",
            content=[
                PJXTooltipTrigger(id="tr", content="Hover me"),
                PJXTooltipContent(id="tc", content="Tip text"),
            ],
        ),
        tooltip_session,
    )
    assert html == (
        '<span id="tt" class="pjx-tooltip" data-pjx-tooltip-placement="bottom">'
        '<span id="tr" class="pjx-tooltip__trigger" tabindex="0">Hover me</span>'
        '<span id="tc" class="pjx-tooltip__tip" role="tooltip" hidden>Tip text</span>'
        "</span>"
    )

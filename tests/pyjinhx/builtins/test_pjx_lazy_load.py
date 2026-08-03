"""PJXLazyLoad — v0.x field/markup parity on the v2 engine."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.pjx_lazy_load import PJXLazyLoad
from pyjinhx.render import render
from pyjinhx.session import RenderSession


class TestFields:
    def test_defaults(self):
        lazy = PJXLazyLoad(id="lz", url="/x")
        assert lazy.when == "viewport"
        assert lazy.trigger == ""
        assert lazy.swap == "outerHTML"
        assert lazy.tag == "div"
        assert lazy.content == ""
        assert lazy.error == ""
        assert lazy.error_text == "Failed to load."
        assert lazy.class_name == ""
        assert lazy.extra_attrs == {}


class TestValidation:
    def test_url_is_required(self):
        with pytest.raises(ValidationError):
            PJXLazyLoad(id="lz")  # type: ignore[call-arg]

    def test_invalid_when_raises(self):
        with pytest.raises(ValidationError):
            PJXLazyLoad(id="lz", url="/x", when="hover")  # type: ignore[arg-type]

    def test_invalid_tag_raises(self):
        with pytest.raises(ValidationError):
            PJXLazyLoad(id="lz", url="/x", tag="span")  # type: ignore[arg-type]

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXLazyLoad(id="lz", url="/x", bogus="x")  # type: ignore[call-arg]


@pytest.fixture
def session():
    return RenderSession(template_dir="/")


def _html(session, **kwargs) -> str:
    base = {"id": "lz", "url": "/x"}
    base.update(kwargs)
    return render(PJXLazyLoad(**base), session)  # type: ignore[arg-type]


class TestRender:
    def test_default_root_is_a_marked_div_with_htmx_attrs(self, session):
        html = _html(session, url="/posts/42/comments")
        assert html.startswith('<div id="lz" class="pjx-lazy-load"')
        assert "data-pjx-lazy-load" in html
        assert 'hx-get="/posts/42/comments"' in html
        assert 'hx-trigger="revealed"' in html
        assert 'hx-swap="outerHTML"' in html
        assert html.endswith("</div>")

    @pytest.mark.parametrize(
        ("when", "expected"),
        [
            ("viewport", "revealed"),
            ("reveal", "pjx:reveal from:closest [data-pjx-region] once"),
            ("load", "load"),
        ],
    )
    def test_when_maps_to_hx_trigger(self, session, when, expected):
        assert f'hx-trigger="{expected}"' in _html(session, when=when)

    def test_explicit_trigger_overrides_when(self, session):
        html = _html(session, when="load", trigger="click once")
        assert 'hx-trigger="click once"' in html

    def test_custom_swap(self, session):
        assert 'hx-swap="innerHTML"' in _html(session, swap="innerHTML")

    def test_string_content_renders_inside_the_root(self, session):
        # pyjinhx's Slot exemption (unlike v0.x's) only makes BaseComponent
        # values render raw via ComponentNode; a plain str in a Slot field
        # still goes through Jinja's autoescape — verified against
        # tests/pyjinhx/builtins/test_pjx_table_cell.py::test_string_content_is_escaped
        # and by direct reproduction against build_context/render_level.
        assert _html(session, content="Loading&hellip;").endswith(
            "Loading&amp;hellip;</div>"
        )

    def test_component_content_renders_inside_the_root(self, session):
        from pyjinhx.builtins.ui.pjx_badge import PJXBadge

        html = _html(session, content=PJXBadge(id="b1", label="soon"))
        assert 'id="b1"' in html
        assert html.index('hx-get="/x"') < html.index('id="b1"')

    @pytest.mark.parametrize("tag", ["div", "tr", "li"])
    def test_tag_selects_the_single_root_element(self, session, tag):
        html = _html(session, tag=tag)
        assert html.startswith(f"<{tag} ")
        assert html.endswith(f"</{tag}>")

    def test_extra_attrs_surface_on_the_dynamic_root(self, session):
        html = _html(session, tag="tr", extra_attrs={"data-k": "v"})
        assert html.startswith("<tr ")
        assert 'data-k="v"' in html[: html.index(">")]

    def test_class_name_is_appended_to_the_root_class(self, session):
        assert 'class="pjx-lazy-load compact"' in _html(session, class_name="compact")


class TestErrorAffordance:
    def test_default_error_text_rides_on_the_root(self, session):
        assert 'data-pjx-error-text="Failed to load."' in _html(session)

    def test_custom_error_text(self, session):
        html = _html(session, error_text="Could not load comments")
        assert 'data-pjx-error-text="Could not load comments"' in html

    def test_error_string_is_escaped_inside_the_template(self, session):
        # A plain string in a Slot field still autoescapes in pyjinhx (only
        # BaseComponent values render raw) — see the TestRender note above.
        html = _html(session, error="<p>Boom</p>")
        assert (
            "<template data-pjx-lazy-error>&lt;p&gt;Boom&lt;/p&gt;</template>" in html
        )

    def test_error_component_renders_raw_inside_the_template(self, session):
        from pyjinhx.builtins.ui.pjx_badge import PJXBadge

        html = _html(session, error=PJXBadge(id="e1", label="offline"))
        assert "<template data-pjx-lazy-error>" in html
        assert 'id="e1"' in html
        assert html.index("<template") < html.index('id="e1"')

    def test_no_error_slot_omits_the_template_entirely(self, session):
        assert "<template data-pjx-lazy-error" not in _html(session)


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXLazyLoad.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_lazy_load.css"
        assert css[0].is_file()

    def test_script_is_frozen_on_the_descriptor(self):
        """First v2 builtin shipping a co-located ``.js``: the stem walk must
        find it beside the ``.pjx``/``.py`` exactly as it finds the ``.css``."""
        js = PJXLazyLoad.__pjx_descriptor__.js_paths
        assert len(js) == 1
        assert js[0].name == "pjx_lazy_load.js"
        assert js[0].is_file()

    def test_render_accumulates_both_assets_into_the_session(self, session):
        # RenderSession does not auto-subscribe accumulate_assets — verified
        # against tests/pyjinhx/test_asset_emission.py, which always does
        # `session.on_rendered.append(accumulate_assets)` explicitly before
        # asserting on css_assets/js_assets. A bare render() leaves both sets
        # empty regardless of the descriptor's asset paths.
        from pyjinhx.session import accumulate_assets

        session.on_rendered.append(accumulate_assets)
        _html(session)
        assert {p.name for p in session.css_assets} == {"pjx_lazy_load.css"}
        assert {p.name for p in session.js_assets} == {"pjx_lazy_load.js"}


class TestScrollSentinel:
    def test_sentinel_row_carries_the_next_cursor_and_replaces_itself(self, session):
        """Infinite scroll is a usage pattern, not a component: the server emits
        a ``tag="tr"`` lazy load as the last row, carrying the next cursor."""
        html = render(
            PJXLazyLoad(id="sentinel", url="/rows?cursor=20", tag="tr"), session
        )
        assert html.startswith('<tr id="sentinel"')
        assert 'hx-get="/rows?cursor=20"' in html
        assert 'hx-trigger="revealed"' in html
        assert 'hx-swap="outerHTML"' in html

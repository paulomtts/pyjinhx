"""PJXButton — v0.x field/markup parity on the v2 engine.

Port of tests/unit/test_button.py. v0.x's golden snapshots
(tests/unit/golden/button_default.html, button_loading.html) do not carry
over: v2 builtins assert on rendered substrings, like every sibling port.
"""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_button import PJXButton


class TestFields:
    def test_defaults(self):
        button = PJXButton(id="b")
        assert button.variant == "default"
        assert button.block is False
        assert button.loading is False
        assert button.disabled is False
        assert button.type == "button"
        assert button.class_name == ""
        assert button.content == ""
        assert button.extra_attrs == {}

    def test_content_is_a_declared_slot_field(self):
        assert "content" in PJXButton.__pjx_descriptor__.slot_fields

    def test_undeclared_kwarg_raises(self):
        with pytest.raises(ValidationError):
            PJXButton(id="b", bogus="x")  # type: ignore[call-arg]

    def test_inline_attr_kwargs_no_longer_pass_through(self):
        """v0.x accepted ``PJXButton(id="b", **{"hx-post": "/save"})``.

        v2 core is strict (extra="forbid"), so a bare inline attr kwarg is now
        a ValidationError — the #500 narrowing. The behavior it replaces is not
        dropped: pass-through moved to the declared ``extra_attrs`` mapping,
        covered by TestRender.test_extra_attrs_surface_on_the_root.
        """
        with pytest.raises(ValidationError):
            PJXButton(id="b", **{"hx-post": "/save"})  # type: ignore[arg-type]

    @pytest.mark.parametrize("value", ["button", "submit", "reset"])
    def test_type_accepts_each_literal(self, value):
        assert PJXButton(id="b", type=value).type == value

    def test_type_rejects_other_values(self):
        with pytest.raises(ValidationError):
            PJXButton(id="b", type="link")  # type: ignore[arg-type]


from pyjinhx.render import render  # noqa: E402
from pyjinhx.session import RenderSession  # noqa: E402


@pytest.fixture
def session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    ClassDescriptor.template_path is absolute and render() feeds it straight to
    the session's FileSystemLoader; Jinja only resolves an absolute path when
    the loader root is "/". Same fixture shape as the sibling builtin tests.
    """
    return RenderSession(template_dir="/")


def _html(session, **kwargs) -> str:
    base = {"id": "b"}
    base.update(kwargs)
    return render(PJXButton(**base), session)  # type: ignore[arg-type]


class TestRender:
    def test_single_root_button_with_defaults(self, session):
        html = _html(session, content="Save")
        assert html.count("<button") == 1
        assert html.count("</button>") == 1
        assert html.startswith('<button id="b"')
        assert html.endswith("</button>")
        assert 'type="button"' in html
        assert "pjx-button pjx-button--default" in html
        assert "aria-busy" not in html
        assert " disabled" not in html

    def test_content_renders_directly_inside_the_button(self, session):
        html = _html(session, content="Save")
        assert ">Save</button>" in html
        # no wrapper spans — content goes straight into <button>
        assert "pjx-button__" not in html

    def test_variant_class(self, session):
        assert "pjx-button--primary" in _html(session, content="Go", variant="primary")

    def test_block_class(self, session):
        assert "pjx-button--block" in _html(session, content="Go", block=True)

    def test_no_block_class_by_default(self, session):
        assert "pjx-button--block" not in _html(session, content="Go")

    def test_disabled_sets_the_attribute(self, session):
        html = _html(session, content="X", disabled=True)
        assert " disabled" in html[: html.index(">")]

    @pytest.mark.parametrize("value", ["button", "submit", "reset"])
    def test_type_renders(self, session, value):
        assert f'type="{value}"' in _html(session, content="X", type=value)

    def test_class_name_is_appended_without_clobbering_base_classes(self, session):
        html = _html(session, content="X", class_name="my-btn")
        assert 'class="pjx-button pjx-button--default my-btn"' in html

    def test_empty_class_name_adds_nothing(self, session):
        assert 'class="pjx-button pjx-button--default"' in _html(session, content="X")

    def test_extra_attrs_surface_on_the_root(self, session):
        html = _html(session, content="X", extra_attrs={"hx-post": "/save"})
        assert 'hx-post="/save"' in html[: html.index(">")]

    def test_content_is_escaped(self, session):
        html = _html(session, content="<script>x</script>")
        assert "&lt;script&gt;x&lt;/script&gt;" in html
        assert "<script>" not in html


class TestAssets:
    def test_stylesheet_is_frozen_on_the_descriptor(self):
        css = PJXButton.__pjx_descriptor__.css_paths
        assert len(css) == 1
        assert css[0].name == "pjx_button.css"
        assert css[0].is_file()

    def test_no_script_asset(self):
        assert PJXButton.__pjx_descriptor__.js_paths == ()


from pyjinhx import discovery  # noqa: E402
from pyjinhx.builtins.pjx_region_loader import PJXRegionLoader  # noqa: E402


@pytest.fixture
def loader_registered():
    """Publish the ``pjx_region_loader`` tag for this test only.

    ``<PJXRegionLoader/>`` in pjx_button.pjx is resolved at render time through
    discovery's tag map (render.py -> get_class), not through a Python import —
    an unclaimed tag is emitted verbatim as passthrough markup instead. The map
    is process-global, so it is snapshotted and restored rather than left
    mutated for whatever test runs next.
    """
    before = discovery._registry.mapping
    discovery.register_class("pjx_region_loader", PJXRegionLoader)
    yield
    discovery._registry.mapping = before


class TestLoading:
    def test_loading_composes_the_region_loader(self, session, loader_registered):
        html = _html(session, content="X", loading=True)
        assert 'aria-busy="true"' in html
        assert 'class="pjx-region-loader"' in html
        assert 'id="b-loader"' in html
        assert 'role="status"' in html

    def test_loading_disables_the_button(self, session, loader_registered):
        html = _html(session, content="X", loading=True)
        assert " disabled" in html[: html.index(">")]

    def test_loader_is_appended_after_the_content(self, session, loader_registered):
        html = _html(session, content="Save", loading=True)
        start = html.index("<button")
        assert html.index("Save", start) < html.index("pjx-region-loader", start)

    def test_button_stays_the_only_button_element(self, session, loader_registered):
        html = _html(session, content="Save", loading=True)
        assert html.count("<button") == 1

    def test_no_loader_when_not_loading(self, session, loader_registered):
        assert "pjx-region-loader" not in _html(session, content="X")

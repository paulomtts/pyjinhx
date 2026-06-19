import pytest

from pyjinhx import Renderer


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def test_scalar_attribute_value_is_escaped():
    from pyjinhx.builtins import PJXAvatar
    html = str(PJXAvatar(id="a", initials="x", alt='" onmouseover="alert(1)').render())
    assert 'onmouseover="alert(1)"' not in html
    assert "&#34;" in html or "&quot;" in html


def test_scalar_text_value_is_escaped():
    from pyjinhx.builtins import PJXCard
    html = str(PJXCard(id="c", title="<script>alert(1)</script>", body="ok").render())
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_loop_derived_value_is_escaped():
    from pyjinhx.builtins import PJXBreadcrumb
    html = str(PJXBreadcrumb(id="b", items=[("<script>x</script>", "/")]).render())
    assert "<script>x</script>" not in html


def test_slot_string_renders_raw():
    from pyjinhx.builtins import PJXCard
    html = str(PJXCard(id="c", title="T", body="<p data-x='1'>hi</p>").render())
    assert "<p data-x='1'>hi</p>" in html  # slot HTML NOT escaped


def test_nested_component_renders_raw():
    from pyjinhx.builtins import PJXCard, PJXBadge
    html = str(PJXCard(id="c", title="T", body=PJXBadge(id="b", label="New")).render())
    assert "pjx-badge" in html and "&lt;span" not in html


def test_collection_slot_text_key_is_escaped():
    from pyjinhx.builtins import PJXTabGroup
    html = str(PJXTabGroup(id="t", tabs={"<script>alert(1)</script>": "<b>panel</b>"}).render())
    assert "<script>alert(1)</script>" not in html      # label (dict key) escaped
    assert "&lt;script&gt;" in html
    assert "<b>panel</b>" in html                          # panel (dict value) raw


def test_markup_value_on_scalar_field_is_still_escaped():
    """Pydantic coerces markupsafe.Markup to plain str on str-typed fields,
    so the safe marker is lost before the context builder runs.  Markup is NOT
    a working escape hatch for scalar fields; use Slot or |safe instead."""
    from markupsafe import Markup
    from pyjinhx.builtins import PJXCard
    html = str(PJXCard(id="c", title=Markup("<b>x</b>"), body="ok").render())
    assert "<b>x</b>" not in html   # still escaped — Markup hatch does NOT work here
    assert "&lt;b&gt;" in html

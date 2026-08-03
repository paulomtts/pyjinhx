"""PJXAccordionContent renders the accordion body region (port of v0.x pyjinhx/builtins/ui/pjx_accordion_content)."""

import dataclasses

import pytest

from pyjinhx.builtins.ui.pjx_accordion_content import PJXAccordionContent
from pyjinhx.component import BaseComponent, Slot
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def content_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession()


def _html(session, **kw) -> str:
    return render(PJXAccordionContent(id="c", **kw), session)


def test_default_render_is_a_single_empty_div(content_session):
    assert _html(content_session) == '<div id="c" class="pjx-accordion__content"></div>'


def test_class_name_appended_to_root(content_session):
    assert 'class="pjx-accordion__content mine"' in _html(
        content_session, class_name="mine"
    )


def test_empty_class_name_adds_nothing(content_session):
    assert 'class="pjx-accordion__content"' in _html(content_session, class_name="")


def test_string_content_renders_raw_inside_root(content_session):
    # ADR 0003: a plain str in a Slot is authored markup, not escaped.
    html = _html(content_session, content="<p>raw</p>")
    assert "<p>raw</p>" in html


class ContentChild(BaseComponent):
    """A minimal component child, to prove a nested component renders inside the region."""

    content: Slot = ""


@pytest.fixture
def content_child_template(tmp_path):
    """Give ContentChild a real template on disk and repoint its descriptor at it."""
    path = tmp_path / "content_child.pjx"
    path.write_text('<span id="{{ id }}" class="child">{{ content }}</span>')
    ContentChild.__pjx_descriptor__ = dataclasses.replace(
        ContentChild.__pjx_descriptor__, template_path=path
    )
    yield path


def test_component_content_renders_inside_root(content_session, content_child_template):
    html = _html(content_session, content=ContentChild(id="k", content="body"))
    assert html.count("<div") == 1
    assert '<span id="k" class="child">body</span>' in html

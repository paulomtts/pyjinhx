"""Tests for PJXModalHeader composable part."""
import re

import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXModalHeader


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def _header(html: str) -> str:
    """Extract only the <header> element."""
    m = re.search(r"<header[\s\S]*?</header>", html)
    return m.group(0) if m else html


def test_modal_header_single_root():
    html = str(PJXModalHeader(id="h1").render())
    assert html.count("<header") == 1


def test_modal_header_id():
    html = str(PJXModalHeader(id="my-header").render())
    assert 'id="my-header"' in html


def test_modal_header_correct_class():
    html = str(PJXModalHeader(id="h2").render())
    assert 'class="pjx-modal__header"' in html


def test_modal_header_class_name_passthrough():
    html = str(PJXModalHeader(id="h3", class_name="custom").render())
    assert 'class="pjx-modal__header custom"' in html


def test_modal_header_title_renders_span():
    html = str(PJXModalHeader(id="h4", title="Hello").render())
    assert '<span id="h4-title" class="pjx-modal__title">Hello</span>' in html


def test_modal_header_no_title_renders_content():
    html = _header(str(PJXModalHeader(id="h5", content="<b>Custom</b>").render()))
    assert "<b>Custom</b>" in html
    assert "pjx-modal__title" not in html


def test_modal_header_close_button_always_present():
    html = str(PJXModalHeader(id="h6").render())
    assert 'class="pjx-modal__close"' in html
    assert "data-pjx-close" in html


def test_modal_header_close_aria_label_default():
    html = str(PJXModalHeader(id="h7").render())
    assert 'aria-label="Close"' in html


def test_modal_header_close_label_custom():
    html = str(PJXModalHeader(id="h8", close_label="Fechar").render())
    assert 'aria-label="Fechar"' in html


def test_modal_header_close_content_default_glyph():
    html = str(PJXModalHeader(id="h9").render())
    assert ">✕</button>" in html


def test_modal_header_close_content_custom():
    html = str(PJXModalHeader(id="h10", close_content="<i class='icon'></i>").render())
    assert "<i class='icon'></i>" in html  # Slot → raw


def test_modal_header_close_button_type():
    html = str(PJXModalHeader(id="h11").render())
    assert 'type="button"' in html

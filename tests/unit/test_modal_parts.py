"""Tests for PJXModalBody and PJXModalFooter composable parts."""
import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXModalBody, PJXModalFooter


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


# ── PJXModalBody ──────────────────────────────────────────────────────────────

def test_modal_body_single_root():
    html = str(PJXModalBody(id="b1", content="Hello").render())
    assert html.count("<div") == 1


def test_modal_body_correct_class():
    html = str(PJXModalBody(id="b2", content="x").render())
    assert 'class="pjx-modal__body"' in html


def test_modal_body_id():
    html = str(PJXModalBody(id="my-body", content="x").render())
    assert 'id="my-body"' in html


def test_modal_body_class_name_passthrough():
    html = str(PJXModalBody(id="b3", content="x", class_name="extra").render())
    assert 'class="pjx-modal__body extra"' in html


def test_modal_body_content_rendered():
    html = str(PJXModalBody(id="b4", content="<p>Hello</p>").render())
    assert "<p>Hello</p>" in html


# ── PJXModalFooter ────────────────────────────────────────────────────────────

def test_modal_footer_single_root():
    html = str(PJXModalFooter(id="f1", content="Footer").render())
    assert html.count("<footer") == 1


def test_modal_footer_correct_class():
    html = str(PJXModalFooter(id="f2", content="x").render())
    assert 'class="pjx-modal__footer"' in html


def test_modal_footer_id():
    html = str(PJXModalFooter(id="my-footer", content="x").render())
    assert 'id="my-footer"' in html


def test_modal_footer_class_name_passthrough():
    html = str(PJXModalFooter(id="f3", content="x", class_name="sticky").render())
    assert 'class="pjx-modal__footer sticky"' in html


def test_modal_footer_content_rendered():
    html = str(PJXModalFooter(id="f4", content="<button>OK</button>").render())
    assert "<button>OK</button>" in html

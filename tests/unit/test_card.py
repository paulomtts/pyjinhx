"""PJXCard: the <article> shell that composes header/body/footer parts."""
import pytest

from pyjinhx import Renderer
from pyjinhx.builtins import PJXCard, PJXCardBody, PJXCardFooter, PJXCardHeader


@pytest.fixture(autouse=True)
def _env(tmp_path):
    Renderer.set_default_environment(str(tmp_path))


def _card(**kw):
    kw.setdefault(
        "content",
        PJXCardHeader(title="Q3 report").render()
        + PJXCardBody(content="Revenue grew 12%.").render()
        + PJXCardFooter(content="Updated today").render(),
    )
    return str(PJXCard(id="c", **kw).render())


def test_single_article_root():
    html = _card()
    assert html.count("<article") == 1
    assert 'class="pjx-card"' in html
    assert 'id="c"' in html


def test_class_name_appends():
    assert 'class="pjx-card mine"' in _card(class_name="mine")


def test_composition_order_header_body_footer():
    html = _card()
    assert html.index("pjx-card__header") < html.index("pjx-card__body") < html.index("pjx-card__footer")
    assert "Q3 report" in html
    assert "Revenue grew 12%." in html
    assert "Updated today" in html


def test_plain_string_content_passes_through():
    html = str(PJXCard(id="c", content="<p>raw</p>").render())
    assert html.count("<article") == 1
    assert "<p>raw</p>" in html
    assert "pjx-card__body" not in html  # shell adds no regions of its own


def test_clean_break_removed_fields():
    for gone in ("title", "header", "body", "footer"):
        assert gone not in PJXCard.model_fields

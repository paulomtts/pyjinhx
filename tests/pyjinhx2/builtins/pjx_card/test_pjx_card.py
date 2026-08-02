"""PJXCard renders the single-root <article> shell that composes the card parts (port of v0.x pyjinhx/builtins/ui/pjx_card)."""

import pytest
from pydantic import ValidationError

from pyjinhx2.builtins.ui.pjx_card import PJXCard
from pyjinhx2.builtins.ui.pjx_card_body import PJXCardBody
from pyjinhx2.builtins.ui.pjx_card_footer import PJXCardFooter
from pyjinhx2.builtins.ui.pjx_card_header import PJXCardHeader
from pyjinhx2.component import BaseComponent, Slot
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession


@pytest.fixture
def card_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXCard(id="c", **kw), session)


def test_default_render_is_single_empty_article(card_session):
    """Missing content renders an empty shell: no error, and no regions of its own."""
    html = _html(card_session)
    assert html == '<article id="c" class="pjx-card"></article>'
    assert "pjx-card__body" not in html


def test_class_name_appended_to_root(card_session):
    assert 'class="pjx-card mine"' in _html(card_session, class_name="mine")


def test_empty_class_name_adds_nothing(card_session):
    assert 'class="pjx-card"' in _html(card_session, class_name="")


def test_component_content_renders_nested(card_session):
    html = _html(card_session, content=PJXCardBody(id="b", content="Revenue grew 12%."))
    assert html.count("<article") == 1
    assert 'class="pjx-card__body"' in html
    assert "Revenue grew 12%." in html


def test_string_content_renders_escaped_inside_root(card_session):
    """v2 narrowing of v0.x: a plain str in a Slot is escaped; only components emit markup."""
    html = _html(card_session, content="<p>raw</p>")
    assert html.count("<article") == 1
    assert "&lt;p&gt;raw&lt;/p&gt;" in html
    assert "<p>raw</p>" not in html


def test_clean_break_removed_fields():
    """v0.x already dropped title/header/body/footer from the shell; v2 must not reintroduce them."""
    for gone in ("title", "header", "body", "footer"):
        assert gone not in PJXCard.model_fields


def test_undeclared_attr_is_rejected():
    """v2 core is strict (extra="forbid"): v0.x's extra_attrs pass-through is gone."""
    with pytest.raises(ValidationError):
        PJXCard(id="c", extra_attrs={"data-x": "y"})  # pyright: ignore[reportCallIssue]


class CardHost(BaseComponent):
    """A three-slot host, so header/body/footer compose in one tree without string joins.

    Not a list-valued single `content` slot: a bare `{{ content }}` interpolation
    never iterates a list (confirmed against tests/pyjinhx2/test_slot_collections.py's
    fixture templates, which all use an explicit `{% for %}` — none of pjx_card's
    templates do). Three named slots is the proven multi-child shape, matching
    `Panel` in tests/pyjinhx2/builtins/test_family_display_primitives_sweep.py.
    """

    head: Slot = ""
    body: Slot = ""
    foot: Slot = ""


@pytest.fixture
def card_host_dir(tmp_path):
    """Give CardHost a real template and register it, so it has a resolvable descriptor.

    A class defined ad hoc in a test module still runs BaseComponent.__init_subclass__,
    which resolves a template *candidate* co-located with the test file — a path
    that does not exist on disk, so rendering would raise TemplateNotFound. Write
    the template under tmp_path and repoint CardHost.__pjx_descriptor__ at it,
    exactly as the sweep test's `family_dir` fixture does for its own `Panel`/`Wrapper` hosts.
    """
    import dataclasses

    host_path = tmp_path / "card_host.pjx"
    host_path.write_text(
        '<div id="{{ id }}" class="card-host">{{ head }}{{ body }}{{ foot }}</div>'
    )
    CardHost.__pjx_descriptor__ = dataclasses.replace(
        CardHost.__pjx_descriptor__, template_path=host_path
    )
    yield tmp_path


def test_composition_order_header_body_footer(card_session, card_host_dir):
    """Header, body and footer render in document order inside one article root."""
    html = render(
        PJXCard(
            id="c",
            content=CardHost(
                id="host",
                head=PJXCardHeader(id="h", title="Q3 report"),
                body=PJXCardBody(id="b", content="Revenue grew 12%."),
                foot=PJXCardFooter(id="f", content="Updated today"),
            ),
        ),
        card_session,
    )
    assert html.count("<article") == 1
    assert (
        html.index("pjx-card__header")
        < html.index("pjx-card__body")
        < html.index("pjx-card__footer")
    )
    assert "Q3 report" in html
    assert "Revenue grew 12%." in html
    assert "Updated today" in html

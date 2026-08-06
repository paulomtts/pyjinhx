"""PJXSelect — the option-list filter input.

The filter is presentation-only: it hides option buttons in the browser and
never touches the native <select> or any selection state. Keyboard nav (#868)
and the exhaustive cross-cutting suite (#869) are separate subtasks.
"""

import pytest

from pyjinhx.builtins.ui.pjx_select import PJXSelect, SelectOption
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession

FRUITS = [
    "Apple",
    "Banana",
    "Cherry",
    "Date",
    "Elderberry",
    "Fig",
    "Grape",
    "Honeydew",
    "Iceberg",
    "Jackfruit",
]


def options(count: int) -> list[SelectOption]:
    """First ``count`` fruit options, value "o0", "o1", ... in order."""
    return [
        SelectOption(value=f"o{i}", label=FRUITS[i]) for i in range(count)
    ]


class TestFields:
    def test_filter_threshold_default(self):
        assert PJXSelect._FILTER_THRESHOLD == 8

    def test_filter_threshold_matches_the_template(self):
        from pathlib import Path

        template = (
            Path(__file__).resolve().parents[4]
            / "pyjinhx"
            / "builtins"
            / "ui"
            / "pjx_select"
            / "pjx_select.pjx"
        ).read_text()
        assert f"options | length > {PJXSelect._FILTER_THRESHOLD}" in template


@pytest.fixture
def session():
    """Loader rooted at "/" so absolute descriptor template paths resolve."""
    return RenderSession()


def _html(session, **kwargs) -> str:
    base = {"id": "s", "name": "fruit", "options": options(10)}
    base.update(kwargs)
    return render(PJXSelect(**base), session)  # type: ignore[arg-type]


class TestRender:
    def test_no_filter_at_the_threshold(self, session):
        html = _html(session, options=options(8))
        assert "data-pjx-select-filter" not in html

    def test_no_filter_below_the_threshold(self, session):
        html = _html(session, options=options(2))
        assert "data-pjx-select-filter" not in html

    def test_no_filter_for_an_empty_option_list(self, session):
        html = _html(session, options=[])
        assert "data-pjx-select-filter" not in html

    def test_filter_appears_one_past_the_threshold(self, session):
        html = _html(session, options=options(9))
        assert "data-pjx-select-filter" in html

    def test_filter_precedes_the_first_option(self, session):
        html = _html(session)
        assert html.index("data-pjx-select-filter") < html.index(
            "data-pjx-select-option"
        )

    def test_filter_sits_inside_the_panel(self, session):
        html = _html(session)
        panel = html[html.index("data-pjx-select-panel") :]
        assert "data-pjx-select-filter" in panel[: panel.index("</div>")]

    def test_filter_is_a_search_input(self, session):
        html = _html(session)
        assert '<input type="search"' in html

    def test_filter_never_posts(self, session):
        # A name= would make the UI-only input part of the form payload
        # alongside the native <select>.
        html = _html(session)
        filter_tag = html[html.index("data-pjx-select-filter") :]
        assert "name=" not in filter_tag[: filter_tag.index(">")]

    def test_filter_is_disabled_with_the_select(self, session):
        html = _html(session, disabled=True)
        filter_tag = html[html.index("data-pjx-select-filter") :]
        assert " disabled" in filter_tag[: filter_tag.index(">")]

    def test_filter_is_enabled_by_default(self, session):
        html = _html(session)
        filter_tag = html[html.index("data-pjx-select-filter") :]
        assert "disabled" not in filter_tag[: filter_tag.index(">")]

    def test_filter_coexists_with_multi_select_checkboxes(self, session):
        html = _html(session, multiple=True, value=["o0"])
        assert "data-pjx-select-filter" in html
        assert html.count('type="checkbox"') == 10
        assert html.index("data-pjx-select-filter") < html.index(
            'type="checkbox"'
        )

    def test_filter_renders_for_single_select(self, session):
        html = _html(session, value="o3")
        assert "data-pjx-select-filter" in html
        assert 'type="checkbox"' not in html

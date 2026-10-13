"""Doc-lint: the roster picker guide matches the shipped roster picker.

The guide names classes, attributes, tokens, events and props by hand, and its
quick start is code a reader copies. These tests run the published snippets as
written and check every name the guide uses against the sources, both ways, so
neither side can drift without a failure here.
"""

import html
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from pyjinhx.builtins import (
    PJXRosterChip,
    PJXRosterItem,
    PJXRosterPicker,
    PJXRosterResults,
)

_ROOT = Path(__file__).resolve().parents[2]
_GUIDE = _ROOT / "docs" / "guide" / "roster-picker.md"

# Built by the component from other fields, never passed by the app.
_DERIVED = {"chips", "visuals", "add_icons", "sentinel", "visual", "remove_icon"}
# Every component takes these; the guide says so once instead of per table.
_COMMON = {"id", "class_name", "extra_attrs"}


def _guide() -> str:
    return _GUIDE.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """The body under ``heading`` up to the next heading of its level or above.

    Lines inside fenced code blocks are skipped when looking for headings, so a
    ``# comment`` in a snippet does not end the section.
    """
    level = len(heading) - len(heading.lstrip("#"))
    lines = text.splitlines()
    start = lines.index(heading) + 1
    in_fence = False
    for end in range(start, len(lines)):
        line = lines[end]
        if line.startswith("```"):
            in_fence = not in_fence
        match = re.match(r"(#+) ", line)
        if not in_fence and match and len(match.group(1)) <= level:
            return "\n".join(lines[start:end])
    return "\n".join(lines[start:])


def _snippet(heading: str) -> str:
    """The first python block under ``heading``."""
    match = re.search(r"```python\n(.*?)```", _section(_guide(), heading), re.DOTALL)
    assert match, f"no python block under {heading}"
    return match.group(1)


@pytest.fixture
def client():
    """The quick start's app, run exactly as the guide prints it."""
    namespace: dict[str, Any] = {}
    exec(_snippet("## Quick start"), namespace)  # noqa: S102 — the published snippet
    with TestClient(namespace["app"]) as test_client:
        yield test_client


def _first_page(client: TestClient) -> str:
    response = client.get("/people", params={"q": "", "picker_id": "team"})
    assert response.status_code == 200
    return response.text


def _values(page: str) -> list[str]:
    return re.findall(r'data-pjx-roster-pick data-value="([^"]*)"', page)


def _next_url(page: str) -> str | None:
    """The sentinel's URL, unescaped: the attribute renders its & as &amp;."""
    match = re.search(r'data-pjx-lazy-load hx-get="([^"]*)"', page)
    return html.unescape(match.group(1)) if match else None


def _walk_pages(client: TestClient, params: dict[str, str]) -> list[str]:
    """Every value the route serves for one search, following each sentinel."""
    page = client.get("/people", params=params).text
    seen = _values(page)
    while (url := _next_url(page)) is not None:
        page = client.get(url).text
        seen += _values(page)
    return seen


def test_guide_is_in_the_nav_after_graph():
    lines = (_ROOT / "mkdocs.yml").read_text(encoding="utf-8").splitlines()
    graph = next(i for i, line in enumerate(lines) if "Graph: guide/graph.md" in line)

    assert lines[graph + 1].strip() == "- Roster Picker: guide/roster-picker.md"
    assert lines[graph + 1].index("-") == lines[graph].index("-")


def test_quick_start_snippet_serves_a_results_page(client):
    page = _first_page(client)

    assert "data-pjx-roster-results" in page
    assert _values(page)
    assert 'id="team-more-' in page
    assert 'hx-trigger="intersect once root:#team-results"' in page


def test_quick_start_snippet_honours_exclude_and_q(client):
    excluded = _values(_first_page(client))[0]

    page = client.get(
        "/people", params={"q": "", "exclude": excluded, "picker_id": "team"}
    ).text
    nothing = client.get(
        "/people", params={"q": "no such person", "picker_id": "team"}
    ).text

    assert f'data-value="{excluded}"' not in page
    assert "pjx-roster-picker__empty" in nothing
    assert "data-pjx-lazy-load" not in nothing


def test_quick_start_snippet_next_url_carries_the_search(client):
    first = _first_page(client)
    url = _next_url(first)
    assert url, "the first page has no sentinel"

    response = client.get(url)

    assert response.status_code == 200
    assert "data-pjx-roster-results" in response.text
    second = _values(response.text)
    assert second
    assert not set(second) & set(_values(first))


def test_quick_start_page_renders_the_picker(client):
    response = client.get("/team")

    assert response.status_code == 200
    assert "data-pjx-roster-picker" in response.text
    assert 'id="team-results"' in response.text
    assert re.search(r'<input type="hidden"[^>]*name="members"', response.text)


def test_quick_start_search_without_picker_id_is_refused(client):
    assert client.get("/people", params={"q": ""}).status_code == 422


def test_quick_start_snippet_matches_q_ignoring_case(client):
    page = client.get("/people", params={"q": "ADA", "picker_id": "team"}).text

    assert _values(page) == ["ada"]


def test_quick_start_paging_ends_after_the_last_row(client):
    seen = _walk_pages(client, {"q": "", "picker_id": "team"})

    assert sorted(seen) == ["ada", "alan", "edsger", "grace"]


def test_quick_start_next_pages_keep_the_exclude(client):
    seen = _walk_pages(client, {"q": "", "exclude": "alan", "picker_id": "team"})

    assert sorted(seen) == ["ada", "edsger", "grace"]


def test_updating_snippet_chip_posts_under_the_picker_name():
    # The update snippet adds a route to the quick start's app, as the guide says.
    source = _snippet("## Quick start") + _snippet("## Updating a picker")
    namespace: dict[str, Any] = {}
    exec(source, namespace)  # noqa: S102 — the published snippets
    with TestClient(namespace["app"]) as test_client:
        response = test_client.post("/team/lead")

    assert response.status_code == 200
    assert "data-pjx-roster-chip" in response.text
    assert re.search(r'<input type="hidden"[^>]*name="members"', response.text)


def test_api_section_documents_values_open_close_only():
    guide = _guide()
    api = _section(guide, "### `window.pjx.rosterPicker`")

    for call in ("values(root)", "open(root)", "close(root)"):
        assert f"pjx.rosterPicker.{call}" in api
    # placement is exposed only for a unit test, never as API.
    assert "placement(" not in guide
    assert "rosterPicker.placement" not in guide


@pytest.mark.parametrize(
    "model", [PJXRosterItem, PJXRosterPicker, PJXRosterResults, PJXRosterChip]
)
def test_props_tables_list_every_user_facing_field(model):
    table = _section(_guide(), f"### {model.__name__}")
    documented = set(re.findall(r"^\| `(\w+)` \|", table, re.MULTILINE))

    fields = set(model.model_fields) - _DERIVED - _COMMON
    assert fields - documented == set()

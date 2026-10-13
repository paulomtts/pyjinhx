# Roster Picker

The roster picker is a server-searched multi-picker. The user types into a search box, picks people
(or anything else) from the rows the server sends back, and each pick becomes a removable chip whose
hidden input posts with the form. The app supplies one search route. The JavaScript and CSS ship
with the component, so there is no script call. The engine is headless: it opens, searches, picks
and removes, then reports what the user did as `pjx:roster-picker:*` events. It is a separate family
from `PJXSelect`, which stays the select for a fixed list of options.

## Quick start

```python
from urllib.parse import urlencode

from fastapi import FastAPI

from pyjinhx import setup
from pyjinhx.builtins import PJXRosterItem, PJXRosterPicker, PJXRosterResults

app = FastAPI()
setup(app)

PAGE_SIZE = 2

PEOPLE: list[PJXRosterItem] = [
    PJXRosterItem(value="ada", label="Ada Lovelace", subtitle="Analyst", initials="AL"),
    PJXRosterItem(
        value="alan", label="Alan Turing", subtitle="Logician", initials="AT"
    ),
    PJXRosterItem(
        value="grace", label="Grace Hopper", subtitle="Admiral", initials="GH"
    ),
    PJXRosterItem(
        value="edsger", label="Edsger Dijkstra", subtitle="Professor", initials="ED"
    ),
]


@app.get("/team")
def team():
    return PJXRosterPicker(
        id="team",
        name="members",
        candidates_url="/people",
        items=[PEOPLE[0]],
    )


@app.get("/people")
def people(picker_id: str, q: str = "", exclude: str = "", cursor: int = 0):
    excluded = set(exclude.split(",")) if exclude else set()
    matches = [
        person
        for person in PEOPLE
        if q.lower() in person.label.lower() and person.value not in excluded
    ]
    page = matches[cursor : cursor + PAGE_SIZE]
    next_cursor = cursor + PAGE_SIZE
    next_url = ""
    if next_cursor < len(matches):
        # The sentinel fetches this URL on its own, so it carries the search too.
        query = {
            "q": q,
            "exclude": exclude,
            "picker_id": picker_id,
            "cursor": next_cursor,
        }
        next_url = "/people?" + urlencode(query)
    return PJXRosterResults(
        items=page,
        picker_id=picker_id,
        next_url=next_url,
        next_cursor=str(next_cursor) if next_url else "",
    )
```

There is no script call. Give the picker a stable `id`: the results list's id (`<id>-results`), the
`picker_id` the search sends and the paging sentinel are all built from it. `picker_id` has no
default in the route, so a request without it is answered with a 422 instead of a page that cannot
find its picker.

`PJXRosterPicker` is built in Python. Its `items` is a list of models, which a `.pjx` tag cannot
pass, as with `PJXSelect`'s `options`.


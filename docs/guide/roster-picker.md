# Roster Picker

The roster picker is a server-searched multi-picker. The user types into a search box, picks people
(or anything else) from the rows the server sends back, and each pick becomes a removable chip whose
hidden input posts with the form. The app supplies one search route. The JavaScript and CSS ship
with the component, so there is no script call. The engine is headless: it opens, searches, picks
and removes, then reports what the user did as `pjx:roster-picker:*` events. It is a separate family
from `PJXSelect`, which stays the select for a fixed list of options;
[ADR 0005](../decisions/0005-roster-picker.md) records why.

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


## Components

Every component also takes `id`, `class_name` and `extra_attrs`, as described in
[Builtin conventions](builtin-conventions.md#the-contract). The tables below list the other props.
Text props are escaped. `Slot` props render raw HTML, so escape any plain text the app puts in them.

### PJXRosterItem

One entry, shown as a chip or a result row. It is a frozen pydantic model, not a component, so it
takes no `id`, `class_name` or `extra_attrs`.

| Prop | Type | Default | Meaning |
|---|---|---|---|
| `value` | `str` | required | Non-empty. The value the chip's hidden input posts. |
| `label` | `str` | required | Non-empty. The name shown on the chip and the row. |
| `subtitle` | `str` | `""` | A second line on the result row. Chips do not show it. |
| `initials` | `str` | `""` | Shown in the avatar when there is no `src`. |
| `color` | `str` | `""` | The avatar's background color. |
| `src` | `str` | `""` | The avatar's image URL. |
| `icon` | `str` | `""` | An icon name. When set, the icon replaces the avatar. |
| `extra` | `Slot` | `""` | Raw HTML beside the chip's label. |
| `detail` | `Slot` | `""` | Raw HTML in a second row under the chip. |

### PJXRosterPicker

The picker: the search box, the results list, the chips, the limit hint and, when required, the
validity input.

| Prop | Type | Default | Meaning |
|---|---|---|---|
| `name` | `str` | required | Non-empty. Each chip's hidden input posts under this name. |
| `candidates_url` | `str` | required | Non-empty. The search route. See [Search route contract](#search-route-contract). |
| `items` | `list[PJXRosterItem]` | `[]` | The initial selection, one chip each, in order. |
| `max_items` | `int` | `0` | The most chips the picker takes. `0` means no limit. See [Behaviour](#behaviour). |
| `required` | `bool` | `False` | Blocks form submit while nothing is chosen. |
| `disabled` | `bool` | `False` | Shows the chips only: no search box, no remove buttons. The selection still submits. |
| `portal` | `bool` | `False` | Moves the open list to `document.body`, for ancestors that clip it. |
| `placeholder` | `str` | `"Search…"` | The search box's placeholder. |
| `remove_label` | `str` | `"Remove"` | Each remove button's `aria-label` starts with it. |
| `limit_label` | `str` | `"Limit reached"` | The hint shown while the picker is full. |
| `empty_message` | `str` | `"No results"` | Written to `data-empty-message` on the root. |

An empty `name` or `candidates_url`, a negative `max_items`, two items with the same `value`, or
more items than a non-zero `max_items` raises a `pydantic.ValidationError`.

### PJXRosterResults

One page of search results: what the search route returns.

| Prop | Type | Default | Meaning |
|---|---|---|---|
| `items` | `list[PJXRosterItem]` | `[]` | The rows on this page, one pick button each. |
| `picker_id` | `str` | required | The picker's `id`. Non-empty, no whitespace. |
| `next_url` | `str` | `""` | Where the next page is. `""` means this is the last page. |
| `next_cursor` | `str` | `""` | Added to the sentinel's id, so each page's sentinel id is unique. |
| `empty_message` | `str` | `"No results"` | Shown when `items` is empty. |
| `remove_label` | `str` | `"Remove"` | The `remove_label` of the chips a pick adds. |

With no items, the page renders `empty_message` and no sentinel. With items and a `next_url`, the
page ends with a `PJXLazyLoad` sentinel. Its id is `<picker_id>-more`, plus `-<next_cursor>` when
`next_cursor` is set. It fires on `intersect once root:#<picker_id>-results`, when it scrolls into
view inside the list, and swaps `outerHTML`, so the next page replaces it.

### PJXRosterChip

One selected entry: a hidden input, the avatar or icon, the label, `extra` and the remove button,
then the optional `detail` row.

| Prop | Type | Default | Meaning |
|---|---|---|---|
| `value` | `str` | required | Non-empty. The hidden input's value. |
| `label` | `str` | required | Non-empty. The chip's text. |
| `initials` | `str` | `""` | As on `PJXRosterItem`. |
| `color` | `str` | `""` | As on `PJXRosterItem`. |
| `src` | `str` | `""` | As on `PJXRosterItem`. |
| `icon` | `str` | `""` | As on `PJXRosterItem`. |
| `extra` | `Slot` | `""` | As on `PJXRosterItem`. |
| `detail` | `Slot` | `""` | As on `PJXRosterItem`. |
| `name` | `str` | `""` | The hidden input's name. Must be the picker's `name` for the chip to post with it. |
| `remove_label` | `str` | `"Remove"` | The remove button's `aria-label` is `"<remove_label>: <label>"`. |
| `disabled` | `bool` | `False` | Drops the remove button. The hidden input stays, so the chip still submits. |

The picker builds its chips itself, from `items` and from each result row. An app renders a
`PJXRosterChip` only for a custom layout or a swap; see [Updating a picker](#updating-a-picker).


## Search route contract

The search box sends `GET <candidates_url>` with three parameters:

| Parameter | Value |
|---|---|
| `q` | The text in the search box. |
| `exclude` | The values already chipped, joined with `,`. Read when the request is built. |
| `picker_id` | The picker's `id`. |

Typing searches after a 300 ms pause. The box has `hx-sync="this:replace"`, so a newer search
replaces one still in flight. The answer is swapped into the results list (`innerHTML`).

- An empty `q` is a normal request. Answer it with the first entries, as the quick start does.
- Return `PJXRosterResults(picker_id=picker_id, ...)`.
- Honouring `exclude` is optional. The picker hides any row whose value is already chipped, so a
  route that ignores it still shows no duplicates.
- **Paging.** The next page is fetched by the sentinel, not by the search box, so its request
  carries no `q`, `exclude` or `picker_id` of its own. `next_url` must hold everything the route
  needs: the quick start passes all three plus `cursor`. The new page replaces the sentinel inside
  the list.
- **Values with commas.** `exclude` is joined with `,`, so a value that contains a comma cannot be
  split back reliably. A route that honours `exclude` needs values without commas, or it should
  ignore `exclude` and rely on the picker hiding chipped rows.
- The search box is detached from any enclosing form, so `q` never posts with the form. Only the
  chips' hidden inputs post, each as `<name>=<value>`.
- Reopening the list over the same text sends no request: the rows it holds already answer it. A
  search that fails or is aborted keeps the rows it would have replaced.

## Behaviour

- **Open and close.** A click on the search box, or focus arriving on it, opens the list and
  searches for the box's text. Typing into a closed list opens it. A pick, focus leaving the box
  and its list, or Escape closes it. Closing hides the rows but keeps them.
- **Pick and remove.** A pick appends the result's chip, or replaces the chip when `max_items=1`.
  It then clears the box and puts focus back in it. Removing a chip moves focus to the next chip's
  remove button, or to the box when there is none.
- **Limit.** `max_items=0` takes any number of chips. `max_items=1` swaps its chip on each pick and
  is never full. With `max_items` above 1, the picker is full once it holds that many chips: the
  search box is disabled, the hint shows `limit_label`, and focus goes to the new chip's remove
  button. Removing a chip undoes all three. A picker rendered with `max_items` items starts full.
- **Required.** `required=True` adds a visually hidden `input.pjx-roster-picker__validity` with
  `required`. It has no `name`, so it never posts. While nothing is chosen it blocks form submit.
  When the browser reports it invalid, the search box takes focus and gets `aria-invalid="true"`,
  and the root gets `pjx-roster-picker--invalid`. The next pick clears both. A required picker's
  box also has `aria-required="true"`.
- **Disabled.** A disabled picker renders no search box and no remove buttons. The chips' hidden
  inputs stay, so the selection still submits. Its validity input is disabled too, so a disabled
  picker never blocks its form.
- **Portal.** With `portal=True`, the open list moves to `document.body` and is fixed under the
  search box, so an `overflow: hidden` or `auto` ancestor cannot clip it. It goes back into the
  picker when it closes. `PJXSelect(portal=True)` offers the same escape hatch, though it moves its
  whole root.
- **Placement.** The list opens under the search box, or above it
  (`pjx-roster-picker__results--above`) when there is not room for it below. Its height is capped by
  `--pjx-roster-picker-max-h` and by the room on that side. It is placed again when the window is
  resized or an ancestor scrolls.
- **Keyboard.** ArrowDown in the open search box moves focus to the first visible result. Results
  are buttons, so Tab reaches them and Enter or Space picks. Escape closes the list and returns
  focus to the box. Escape on a closed list is left alone, so it reaches an enclosing dialog. There
  is no ArrowUp, Enter, Home or End roving from the box, and no `aria-activedescendant`.

## Updating a picker

Every update is a plain htmx swap of server-rendered markup. The picker listens on the document, so
nothing needs rebinding after a swap.

- **Swap the whole picker.** Re-render `PJXRosterPicker` with the same `id` and new `items`, and swap
  it over the old one.
- **Swap one chip or the chip list.** A swap that adds or removes chips, including an `outerHTML`
  swap whose answer is empty, brings the limit, the hint, the validity input and the hidden result
  rows back in step with the chips.

A swap fires no `pjx:roster-picker:*` events. Those report what the user did, not what the server
changed.

This route adds a chip from the server. A button with `hx-post="/team/lead"`,
`hx-target="#team .pjx-roster-picker__chips"` and `hx-swap="beforeend"` appends it to the picker
from the quick start:

```python
from pyjinhx.builtins import PJXRosterChip


@app.post("/team/lead")
def add_lead():
    # Chips the picker builds get its name; a hand-rendered one needs it too,
    # or its hidden input posts under no name.
    return PJXRosterChip(value="grace", label="Grace Hopper", name="members")
```

## Events and JavaScript API

### Event list

Every event is dispatched on the picker root and bubbles. A `before-*` event is cancelable:
`event.preventDefault()` refuses the pick or keeps the chip. `detail` carries the value, not the
`{reason, trigger}` of the overlay builtins: a pick has no dismiss reason.

| Event | `detail` | Cancelable | Fired when |
|---|---|---|---|
| `pjx:roster-picker:before-pick` | `{value}` | yes | A result is about to be added. |
| `pjx:roster-picker:pick` | `{value}` | no | The chip was added. |
| `pjx:roster-picker:before-remove` | `{value}` | yes | A chip is about to be dropped. |
| `pjx:roster-picker:remove` | `{value}` | no | The chip was dropped. |
| `pjx:roster-picker:change` | `{values}` | no | After each pick or remove, once, with every chip's value in chip order. |

```js
document.getElementById("team").addEventListener("pjx:roster-picker:before-remove", (event) => {
    // The team's owner cannot be taken off it.
    if (event.detail.value === "ada") event.preventDefault();
});
```

### `window.pjx.rosterPicker`

| Call | Returns |
|---|---|
| `pjx.rosterPicker.values(root)` | A new array of the chips' values, in chip order. |
| `pjx.rosterPicker.open(root)` | `true`. Opens the list and searches, as a click does. A reopen over the same text sends no request. Focus does not move. |
| `pjx.rosterPicker.close(root)` | `true`. Closes the list and keeps its rows. Focus does not move. |

`open` and `close` return `false` and change nothing when the picker is disabled or full. All three
throw `Error("pjx.rosterPicker.<name>: expected a roster picker root ([data-pjx-roster-picker])")`
when `root` is anything but the picker root.


## Theming

The picker reads these `--pjx-roster-picker-*` tokens, set on `:where(:root)`. Override them
globally or on one picker, as described in [Builtin conventions](builtin-conventions.md#theming).

| Area | Tokens |
|---|---|
| Colors | `--pjx-roster-picker-bg`, `--pjx-roster-picker-fg`, `--pjx-roster-picker-muted`, `--pjx-roster-picker-border`, `--pjx-roster-picker-focus`, `--pjx-roster-picker-invalid` |
| Shape | `--pjx-roster-picker-radius`, `--pjx-roster-picker-padding`, `--pjx-roster-picker-gap` |
| Chips | `--pjx-roster-picker-chip-bg` |
| Results list | `--pjx-roster-picker-results-bg`, `--pjx-roster-picker-shadow`, `--pjx-roster-picker-z`, `--pjx-roster-picker-max-h`, `--pjx-roster-picker-min-h`, `--pjx-roster-picker-room` |
| Rows | `--pjx-roster-picker-row-hover`, `--pjx-roster-picker-row-active` |

`--pjx-roster-picker-room` is written by the script while the list is open: the room on the side the
list opens on. It defaults to `--pjx-roster-picker-max-h`. Do not set it yourself.

To restyle the block, scope your rules under an app class
(`.team-form .pjx-roster-picker__chip { ... }`). Do not redefine `.pjx-roster-picker*` rules
unscoped.

## DOM contract

These classes, attributes, events and states are versioned API.

### Classes

| Class | Element |
|---|---|
| `.pjx-roster-picker` | Picker root |
| `.pjx-roster-picker__search` | Wraps the search box and its results list |
| `.pjx-roster-picker__input` | The search box |
| `.pjx-roster-picker__results` | The results list (`#<id>-results`) |
| `.pjx-roster-picker__results--above` | The results list, opened above the box |
| `.pjx-roster-picker__results-page` | One `PJXRosterResults` page |
| `.pjx-roster-picker__pick` | A result row (a button) |
| `.pjx-roster-picker__pick-avatar`, `.pjx-roster-picker__pick-icon`, `.pjx-roster-picker__pick-text`, `.pjx-roster-picker__pick-label`, `.pjx-roster-picker__pick-subtitle`, `.pjx-roster-picker__pick-add` | Result row parts |
| `.pjx-roster-picker__empty` | The `empty_message` paragraph |
| `.pjx-roster-picker__more` | The paging sentinel |
| `.pjx-roster-picker__chips` | The chip list |
| `.pjx-roster-picker__chip` | Chip root |
| `.pjx-roster-picker__chip-input` | The chip's hidden input |
| `.pjx-roster-picker__chip-row`, `.pjx-roster-picker__chip-avatar`, `.pjx-roster-picker__chip-icon`, `.pjx-roster-picker__chip-label`, `.pjx-roster-picker__chip-extra`, `.pjx-roster-picker__chip-detail` | Chip parts |
| `.pjx-roster-picker__chip-remove` | The chip's remove button |
| `.pjx-roster-picker__hint` | The limit hint |
| `.pjx-roster-picker__validity` | The hidden input `required` adds |
| `.pjx-roster-picker--invalid` | The root, after a failed submit |

### Attributes

| Attribute | On | Meaning |
|---|---|---|
| `data-pjx-roster-picker` | Picker root | Marks a picker. |
| `data-name`, `data-max-items`, `data-empty-message` | Picker root | The `name`, `max_items` and `empty_message` props. |
| `data-disabled` | Picker root | Present when disabled. |
| `data-pjx-roster-picker-portal` | Picker root | Present with `portal=True`. |
| `role="combobox"`, `aria-autocomplete="list"` | Search box | Always. |
| `aria-expanded` | Search box | `"true"` while the list is open. |
| `aria-controls="<id>-results"` | Search box | Names the results list. |
| `aria-required="true"` | Search box | Present with `required=True`. |
| `aria-invalid="true"` | Search box | Set after a failed submit. |
| `data-last-query` | Search box | Set by the script: the text the shown rows answer. |
| `id="<id>-results"`, `hidden` | Results list | Its id, and `hidden` while closed. |
| `data-pjx-roster-results` | Results page | Marks one page. |
| `data-pjx-roster-pick`, `data-value` | Result row | Marks a row and holds its value. |
| `data-pjx-roster-chip` | Chip root | Marks a chip. |
| `data-pjx-roster-remove` | Remove button | Marks the button that drops its chip. |

### Events

All `pjx:roster-picker:*` events and their `detail` are listed in [Event list](#event-list).

### State

| State | Meaning |
|---|---|
| `[aria-expanded="true"]` on the search box | The list is open. |
| `[hidden]` on the results list | The list is closed. |
| `disabled` on the search box | The picker is full. |
| `[hidden]` on the hint | The picker is not full. |
| `.pjx-roster-picker--invalid` on the root, `aria-invalid` on the box | A submit failed while nothing was chosen. Cleared by the next pick. |
| `.pjx-roster-picker__results--above` on the results list | The list opened above the box. |
| `hidden` on a result row | The row's `data-value` is already chipped. |

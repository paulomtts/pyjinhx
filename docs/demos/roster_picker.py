from pyjinhx.builtins.ui.pjx_roster_picker import PJXRosterItem, PJXRosterPicker
from pyjinhx.builtins.ui.pjx_roster_results import PJXRosterResults

ROUTE = "/demo/people"

# (value, label, role, initials). No src, so the page makes no image requests.
PEOPLE = [
    PJXRosterItem(value=value, label=label, subtitle=role, initials=initials)
    for value, label, role, initials in (
        ("ada", "Ada Lovelace", "Analyst", "AL"),
        ("alan", "Alan Turing", "Logician", "AT"),
        ("grace", "Grace Hopper", "Admiral", "GH"),
        ("edsger", "Edsger Dijkstra", "Professor", "ED"),
        ("barbara", "Barbara Liskov", "Architect", "BL"),
        ("donald", "Donald Knuth", "Author", "DK"),
        ("margaret", "Margaret Hamilton", "Flight software", "MH"),
        ("ken", "Ken Thompson", "Systems", "KT"),
        ("radia", "Radia Perlman", "Networking", "RP"),
        ("john", "John Backus", "Compilers", "JB"),
    )
]

# (picker id, name, max_items, initial items, caption)
PICKERS = (
    (
        "demo-roster-team",
        "team",
        0,
        [PEOPLE[0]],
        "Team: any number of people.",
    ),
    (
        "demo-roster-owner",
        "owner",
        1,
        [PEOPLE[2]],
        "Owner: one person. A pick replaces the chip.",
    ),
    (
        "demo-roster-approvers",
        "approvers",
        3,
        [PEOPLE[4], PEOPLE[3]],
        "Approvers: up to three. One more pick fills it.",
    ),
)


def _answers(picker_id):
    # What the route can send this picker, kept inert until a request: every
    # person on one page closed by a sentinel, which the script trims to the
    # rows it answers, and the empty page. The sentinel's url and cursor are
    # placeholders the script replaces.
    full = PJXRosterResults(
        id=f"{picker_id}-page",
        picker_id=picker_id,
        items=PEOPLE,
        next_url=ROUTE,
        next_cursor="0",
    ).render()
    empty = PJXRosterResults(id=f"{picker_id}-empty", picker_id=picker_id).render()
    return (
        f'<template data-demo-roster-page="{picker_id}">{full}</template>'
        f'<template data-demo-roster-empty="{picker_id}">{empty}</template>'
    )


def roster_picker():
    parts = []
    for picker_id, name, max_items, items, caption in PICKERS:
        picker = PJXRosterPicker(
            id=picker_id,
            name=name,
            candidates_url=ROUTE,
            items=items,
            max_items=max_items,
        ).render()
        parts.append(f"<p>{caption}</p>{picker}{_answers(picker_id)}")
    body = "".join(parts)
    # The demo stage is 360px wide, narrow for chips with avatars.
    return f'<div style="width: min(480px, calc(100vw - 2rem))">{body}</div>'


DEMOS = {"PJXRosterPicker": (roster_picker, 460)}

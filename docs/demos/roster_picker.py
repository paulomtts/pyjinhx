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

# The guide's quick-start route, played in-page because a docs page has no
# server, as the graph demo plays its routes. Each answer is cut from the
# pages rendered into this picker's <template>s and handed to htmx.swap
# against the request's own target, so the swap and the picker's listeners
# are real. Only attributes are set from request values, so a query only
# ever becomes attribute text.
SCRIPT = """<script data-demo-roster-route>
(() => {
  const ROUTE = "/demo/people";
  const PAGE_SIZE = 4;

  function inert(kind, pickerId) {
    const name = "data-demo-roster-" + kind;
    const template = Array.from(document.querySelectorAll("template[" + name + "]"))
      .find((t) => t.getAttribute(name) === pickerId);
    return template && template.content.firstElementChild.cloneNode(true);
  }

  // One page of the people whose label holds q and who are not excluded,
  // closed by a sentinel while more remain. Null for a picker this page
  // does not have.
  function answer(params) {
    const pickerId = params.get("picker_id") || "";
    const full = inert("page", pickerId);
    const empty = inert("empty", pickerId);
    if (!full || !empty) return null;
    const q = params.get("q") || "";
    const exclude = params.get("exclude") || "";
    const excluded = exclude ? exclude.split(",") : [];
    const cursor = Number(params.get("cursor") || 0);
    const rows = Array.from(full.querySelectorAll(":scope > [data-pjx-roster-pick]"));
    const matches = rows.filter((row) => {
      const label = row.querySelector(".pjx-roster-picker__pick-label").textContent;
      return label.toLowerCase().includes(q.toLowerCase()) && !excluded.includes(row.dataset.value);
    });
    const page = matches.slice(cursor, cursor + PAGE_SIZE);
    if (!page.length) {
      empty.id = pickerId + "-page-" + cursor;
      return empty;
    }
    // Each row's chip <template> goes with it.
    rows.filter((row) => !page.includes(row)).forEach((row) => {
      row.nextElementSibling.remove();
      row.remove();
    });
    full.id = pickerId + "-page-" + cursor;
    const sentinel = full.querySelector(":scope > .pjx-roster-picker__more");
    const next = cursor + PAGE_SIZE;
    if (next < matches.length) {
      const query = new URLSearchParams({ q, exclude, picker_id: pickerId, cursor: next });
      sentinel.id = pickerId + "-more-" + next;
      sentinel.setAttribute("hx-get", ROUTE + "?" + query);
    } else {
      sentinel.remove();
    }
    return full;
  }

  // Not bound until the document is parsed: the picker's script comes after
  // this one, and its own beforeRequest listener, which cancels a reopen
  // over the text the kept rows answer, has to run first.
  document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("htmx:beforeRequest", (event) => {
      if (event.defaultPrevented) return;
      const { elt, target, requestConfig } = event.detail;
      const path = requestConfig.path;
      const search = path === ROUTE;
      if (!search && !path.startsWith(ROUTE + "?")) return;
      // A search sends its values; a sentinel carries its search in its url.
      const values = requestConfig.parameters;
      const params = search
        ? new URLSearchParams({
            q: values.q || "",
            exclude: values.exclude || "",
            picker_id: values.picker_id || "",
          })
        : new URL(path, location.href).searchParams;
      const page = answer(params);
      if (!page) return;
      event.preventDefault();
      htmx.swap(target, page.outerHTML, { swapStyle: elt.getAttribute("hx-swap") });
      // A cancelled request never reaches htmx:afterRequest, where the
      // picker records the query its rows answer, so it is recorded here.
      if (search) elt.setAttribute("data-last-query", params.get("q"));
    });
  });
})();
</script>"""


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
    return f'<div style="width: min(480px, calc(100vw - 2rem))">{body}{SCRIPT}</div>'


DEMOS = {"PJXRosterPicker": (roster_picker, 460)}

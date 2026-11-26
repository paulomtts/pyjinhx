"""Asset paths, page URLs and the picker/page helpers the picker browser tests share."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pyjinhx.builtins.pjx_roster_picker import PJXRosterItem, PJXRosterPicker
from pyjinhx.client import read_vendored_htmx
from pyjinhx.rendering.pipeline import render

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page

    from pyjinhx.rendering.session import RenderSession


PICKER_DIR = (
    Path(__file__).resolve().parents[4] / "pyjinhx" / "builtins" / "pjx_roster_picker"
)


CSS = (PICKER_DIR / "pjx_roster_picker.css").read_text(encoding="utf-8")


ASSET = (PICKER_DIR / "pjx_roster_picker.js").read_text(encoding="utf-8")


URL = "http://pjx.test/"


CANDIDATES_URL = "http://pjx.test/candidates"


CANDIDATES = "http://pjx.test/candidates*"


HTMX_TAG = f"<script>{read_vendored_htmx()}</script>"


ASSET_TAG = f"<script>{ASSET}</script>"


OPEN = ("true", False)


CLOSED = ("false", True)


def _picker(session: RenderSession, picker_id: str = "p", **kwargs: Any) -> str:
    return render(
        PJXRosterPicker(
            id=picker_id, name="members", candidates_url=CANDIDATES_URL, **kwargs
        ),
        session,
    )


def _item(value: str) -> PJXRosterItem:
    return PJXRosterItem(value=value, label=value.upper())


def _settle(page: Page) -> None:
    """Let two animation frames and a short beat pass, so a pending handler has run."""
    page.evaluate(
        "() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))"
    )
    # There is no event for "did not fire", so proving a negative needs a beat.
    page.wait_for_timeout(200)


def _input(page: Page, picker_id: str = "p") -> Locator:
    return page.locator(f"#{picker_id} .pjx-roster-picker__input")


def _state(page: Page, picker_id: str = "p") -> tuple[str, bool]:
    """The input's aria-expanded and the mount's hidden, which must agree."""
    expanded, hidden = page.evaluate(
        """id => [
            document.querySelector(`#${id} .pjx-roster-picker__input`).getAttribute('aria-expanded'),
            document.getElementById(`${id}-results`).hidden,
        ]""",
        picker_id,
    )
    return expanded, hidden


def _pick(page: Page, value: str, picker_id: str = "p") -> Locator:
    return page.locator(
        f'#{picker_id}-results [data-pjx-roster-pick][data-value="{value}"]'
    )


def _hidden_rows(page: Page, picker_id: str = "p") -> dict[str, bool]:
    """Each result row's value mapped to its hidden flag."""
    return page.evaluate(
        """id => Object.fromEntries(Array.from(
            document.querySelectorAll(`#${id}-results [data-pjx-roster-pick]`),
            (row) => [row.dataset.value, row.hidden]
        ))""",
        picker_id,
    )


def _has_focus(locator: Locator) -> bool:
    return locator.evaluate("el => el === document.activeElement")


def _hint_hidden(page: Page, picker_id: str = "p") -> bool:
    return page.evaluate(
        "id => document.querySelector(`#${id} .pjx-roster-picker__hint`).hidden",
        picker_id,
    )

from typing import Any

from pydantic import Field, computed_field, field_validator

from pyjinhx import BaseComponent
from pyjinhx.base import AttrValue, ExtraAttrs


class PJXPaginator(BaseComponent):
    page: int
    total_pages: int = Field(ge=1)
    url: str
    target: str = ""
    swap: str = "innerHTML"
    push_url: bool = False
    siblings: int = Field(default=1, ge=0)
    boundaries: int = Field(default=1, ge=0)
    prev_next: bool = True
    first_last: bool = False
    prev_label: str = "Prev"
    next_label: str = "Next"
    first_label: str = "First"
    last_label: str = "Last"
    aria_label: str = "Pagination"
    class_name: AttrValue = ""
    extra_attrs: ExtraAttrs = Field(default_factory=dict)

    @field_validator("url")
    @classmethod
    def _url_has_page_placeholder(cls, value: str) -> str:
        if "{page}" not in value:
            raise ValueError("url must contain the '{page}' placeholder")
        return value

    @property
    def _clamped_page(self) -> int:
        return max(1, min(self.page, self.total_pages))

    def _href(self, n: int) -> str:
        return self.url.replace("{page}", str(n))

    def _window(self) -> list[int]:
        """Sorted page numbers to show, before gap handling."""
        total, bound, sib, page = (
            self.total_pages, self.boundaries, self.siblings, self._clamped_page,
        )
        shown: set[int] = set()
        for n in range(1, min(bound, total) + 1):
            shown.add(n)
        for n in range(max(total - bound + 1, 1), total + 1):
            shown.add(n)
        for n in range(page - sib, page + sib + 1):
            if 1 <= n <= total:
                shown.add(n)
        return sorted(shown)

    def _page_item(self, n: int, current: int) -> dict[str, Any]:
        if n == current:
            return {"kind": "current", "number": n}
        return {"kind": "page", "number": n, "href": self._href(n)}

    def _control(self, variant: str, label: str, target_page: int, *, disabled: bool) -> dict[str, Any]:
        item: dict[str, Any] = {"kind": "control", "variant": variant, "label": label, "disabled": disabled}
        if not disabled:
            item["href"] = self._href(target_page)
        return item

    @computed_field
    @property
    def items(self) -> list[dict[str, Any]]:
        page, total = self._clamped_page, self.total_pages
        out: list[dict[str, Any]] = []
        if self.first_last:
            out.append(self._control("first", self.first_label, 1, disabled=page == 1))
        if self.prev_next:
            out.append(self._control("prev", self.prev_label, page - 1, disabled=page == 1))
        prev_n: int | None = None
        for n in self._window():
            if prev_n is not None:
                if n - prev_n == 2:
                    out.append(self._page_item(prev_n + 1, page))
                elif n - prev_n > 2:
                    out.append({"kind": "ellipsis"})
            out.append(self._page_item(n, page))
            prev_n = n
        if self.prev_next:
            out.append(self._control("next", self.next_label, page + 1, disabled=page == total))
        if self.first_last:
            out.append(self._control("last", self.last_label, total, disabled=page == total))
        return out

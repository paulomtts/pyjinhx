import re
from html.parser import HTMLParser

from .dataclasses import Tag
from .utils import extract_tag_name_from_raw

RE_PASCAL_CASE_TAG_NAME = re.compile(r"^[A-Z](?:[a-z]+(?:[A-Z][a-z]+)*)?$")


class Parser(HTMLParser):
    """
    HTML parser that identifies PascalCase component tags and builds a tree of Tag nodes.

    Standard HTML tags are passed through as raw strings, while PascalCase tags (e.g., `<MyButton>`)
    are parsed into Tag objects for component rendering. After calling `feed(html)`, the parsed
    structure is available in `root_nodes`.

    Attributes:
        root_nodes: List of top-level parsed nodes (Tag objects or raw HTML strings).
    """

    def __init__(self) -> None:
        super().__init__()
        self._stack: list[Tag] = []
        self.root_nodes: list[Tag | str] = []

    def _is_custom_component(self, tag_name: str) -> bool:
        return bool(RE_PASCAL_CASE_TAG_NAME.match(tag_name))

    def _attrs_to_dict(self, attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {attr_name: (attr_value or "") for attr_name, attr_value in attrs}

    def _append_child(self, node: Tag | str) -> None:
        if self._stack:
            self._stack[-1].children.append(node)
        else:
            self.root_nodes.append(node)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = self.get_starttag_text() or f"<{tag}>"
        original_tag_name = extract_tag_name_from_raw(raw) or tag

        if self._is_custom_component(original_tag_name):
            tag_node = Tag(name=original_tag_name, attrs=self._attrs_to_dict(attrs))
            self._stack.append(tag_node)
            return

        self._append_child(raw)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = self.get_starttag_text() or f"<{tag} />"
        original_tag_name = extract_tag_name_from_raw(raw) or tag

        if self._is_custom_component(original_tag_name):
            tag_node = Tag(name=original_tag_name, attrs=self._attrs_to_dict(attrs))
            self._append_child(tag_node)
            return

        self._append_child(raw)

    def handle_endtag(self, tag: str) -> None:
        if self._stack and self._stack[-1].name.lower() == tag.lower():
            tag_node = self._stack.pop()
            self._append_child(tag_node)
            return

        self._append_child(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self._append_child(data)

from dataclasses import dataclass, field

@dataclass
class Tag:
    """
    Represents a parsed HTML/component tag with its attributes and children.

    Used by the Parser to build a tree structure from HTML-like markup containing
    PascalCase component tags (e.g., `<MyButton text="OK">`).

    Attributes:
        name: The tag name (e.g., "MyButton", "div").
        attrs: Dictionary of attribute names to values.
        children: Nested tags or raw text content within this tag.
    """

    name: str
    attrs: dict[str, str]
    children: list["Tag | str"] = field(default_factory=list)
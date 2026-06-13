import os
import re
from functools import lru_cache


def pascal_case_to_snake_case(name: str) -> str:
    """
    Convert a PascalCase/CamelCase identifier into snake_case.

    Consecutive capitals are treated as acronyms (PJXAvatar -> pjx_avatar).

    Args:
        name: The identifier to convert.

    Returns:
        The snake_case version of the identifier.
    """
    return re.sub(
        r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name
    ).lower()


def pascal_case_to_kebab_case(name: str) -> str:
    """
    Convert a PascalCase/CamelCase identifier into kebab-case.

    Args:
        name: The identifier to convert.

    Returns:
        The kebab-case version of the identifier.
    """
    return pascal_case_to_snake_case(name).replace("_", "-")


def component_resolution_classes(component_class: type) -> list[type]:
    """Concrete component classes of an MRO, nearest first.

    Framework classes (BaseComponent, ReactiveComponent) declare
    ``_pjx_framework`` in their own body and are skipped; concrete components
    inherit the attribute without owning it.
    """
    return [
        klass
        for klass in component_class.__mro__
        if hasattr(klass, "_pjx_framework") and "_pjx_framework" not in klass.__dict__
    ]


def tag_name_to_template_filenames(
    tag_name: str, *, extensions: tuple[str, ...] = (".html", ".jinja")
) -> list[str]:
    """
    Convert a component tag name into candidate template filenames.

    Generates candidates with both underscore and hyphen separators.

    Args:
        tag_name: The PascalCase component tag name (e.g., "ButtonGroup").
        extensions: File extensions to use, in order of preference.

    Returns:
        List of candidate filenames (e.g., ["button_group.html", "button-group.html",
        "button_group.jinja", "button-group.jinja"]).
    """
    snake_name = pascal_case_to_snake_case(tag_name)
    kebab_name = snake_name.replace("_", "-")
    candidates = []
    for extension in extensions:
        candidates.append(f"{snake_name}{extension}")
        candidates.append(f"{kebab_name}{extension}")
    return candidates


def normalize_path_separators(path: str) -> str:
    """
    Normalize path separators to forward slashes.

    Args:
        path: The path string to normalize.

    Returns:
        The path with backslashes replaced by forward slashes.
    """
    return path.replace("\\", "/")


def extract_tag_name_from_raw(raw_tag: str) -> str:
    """
    Extract the tag name from a raw HTML start tag string.

    Args:
        raw_tag: The raw HTML tag string (e.g., '<Button text="OK"/>').

    Returns:
        The tag name, or an empty string if not found.

    Example:
        >>> extract_tag_name_from_raw('<Button text="OK"/>')
        'Button'
    """
    match = re.search(r"<\s*([A-Za-z][A-Za-z0-9]*)", raw_tag)
    return match.group(1) if match else ""


def detect_root_directory(
    start_directory: str | None = None,
    project_markers: list[str] | None = None,
) -> str:
    """
    Find the project root by walking upward until a marker file is found.

    Args:
        start_directory: Directory to start searching from. Defaults to current working directory.
        project_markers: Files/directories indicating project root (e.g., "pyproject.toml", ".git").
            Defaults to common markers like pyproject.toml, .git, package.json, etc.

    Returns:
        The detected project root directory, or the start directory if no marker is found.
    """
    current_dir = start_directory or os.getcwd()
    markers = project_markers or [
        "pyproject.toml",
        "main.py",
        ".git",
        ".gitignore",
        "package.json",
        "uv.lock",
    ]

    search_dir = current_dir
    while search_dir != os.path.dirname(search_dir):
        for marker in markers:
            if os.path.exists(os.path.join(search_dir, marker)):
                return search_dir
        search_dir = os.path.dirname(search_dir)

    return current_dir


def _find_first_start_tag(html: str) -> int:
    """
    Return the index of the '<' that opens the first element start tag, skipping
    leading whitespace, HTML comments, doctype, and processing instructions.
    Returns -1 if no start tag is found.
    """
    cursor = 0
    while True:
        cursor = html.find("<", cursor)
        if cursor == -1:
            return -1
        following = html[cursor + 1 : cursor + 2]
        if following in ("!", "?"):
            end = html.find(">", cursor)
            if end == -1:
                return -1
            cursor = end + 1
            continue
        if following.isalpha():
            return cursor
        cursor += 1


def _escape_attr_value(value: str) -> str:
    return str(value).replace(chr(34), "&quot;")


def stamp_root_attributes(html: str, attributes: dict[str, str]) -> str:
    """
    Splice attributes into the first start tag of an HTML fragment.

    Performs a minimal, quote-aware scan to find the end of the first element's
    start tag and inserts the given attributes just before the closing '>' (or
    before the '/' of a '/>' self-closing tag). The rest of the markup is left
    byte-for-byte untouched — no parse/re-serialize round trip.

    Args:
        html: The rendered HTML fragment. Must contain at least one start tag.
        attributes: Attribute name -> value pairs to insert. Values are
            HTML-attribute escaped.

    Returns:
        The HTML with the attributes spliced into the root element's start tag.

    Raises:
        ValueError: If no start tag is found. Reactive components must render a
            single root element.
    """
    if not attributes:
        return html

    tag_open = _find_first_start_tag(html)
    if tag_open == -1:
        raise ValueError(
            "Cannot stamp reactive attributes: no root HTML element found. "
            "Reactive components must render a single root element."
        )

    cursor = tag_open + 1
    length = len(html)
    quote: str | None = None
    while cursor < length:
        char = html[cursor]
        if quote is not None:
            if char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
        elif char == ">":
            break
        cursor += 1
    else:
        raise ValueError("Cannot stamp reactive attributes: unterminated start tag.")

    insert_at = cursor - 1 if html[cursor - 1] == "/" else cursor
    rendered_attrs = "".join(
        f' {name}="{_escape_attr_value(value)}"'
        for name, value in attributes.items()
    )
    return html[:insert_at] + rendered_attrs + html[insert_at:]


def css_attribute_selector_attr_value(value: str) -> str:
    """Escape a value for use inside a CSS attribute selector quoted with single quotes."""
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


@lru_cache(maxsize=1)
def read_client_runtime() -> str:
    """Return the bundled pyjinhx client runtime JavaScript source."""
    runtime_path = os.path.join(os.path.dirname(__file__), "runtime", "pjx.js")
    with open(runtime_path, encoding="utf-8") as runtime_file:
        return runtime_file.read()

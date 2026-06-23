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


TEMPLATE_EXTENSIONS: tuple[str, ...] = (".pjx", ".html", ".jinja")
"""Template file extensions to try, in order of preference."""


def tag_name_to_template_filenames(
    tag_name: str, *, extensions: tuple[str, ...] = TEMPLATE_EXTENSIONS
) -> list[str]:
    """
    Convert a component tag name into candidate template filenames.

    Generates candidates with both underscore and hyphen separators.

    Args:
        tag_name: The PascalCase component tag name (e.g., "ButtonGroup").
        extensions: File extensions to use, in order of preference.

    Returns:
        List of candidate filenames (e.g., ["button_group.pjx", "button-group.pjx",
        "button_group.html", "button-group.html", ...]).
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


def css_attribute_selector_attr_value(value: str) -> str:
    """Escape a value for use inside a CSS attribute selector quoted with single quotes."""
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


@lru_cache(maxsize=1)
def read_client_runtime() -> str:
    """Return the bundled pyjinhx client runtime JavaScript source."""
    runtime_path = os.path.join(os.path.dirname(__file__), "runtime", "pjx.js")
    with open(runtime_path, encoding="utf-8") as runtime_file:
        return runtime_file.read()


def read_vendored_htmx() -> str:
    """Return the bundled htmx source, guarded so it no-ops if htmx is present.

    pjx.js (the reactive transport) depends on htmx. We ship and inline a pinned
    copy ahead of pjx.js on reactive root renders. The ``if (!window.htmx)``
    guard means a page that already loaded its own htmx keeps that copy instead
    of redefining it — so injecting ours is safe even when the user adds htmx.
    """
    htmx_path = os.path.join(os.path.dirname(__file__), "runtime", "htmx.min.js")
    with open(htmx_path, encoding="utf-8") as htmx_file:
        source = htmx_file.read()
    return f"if (!window.htmx) {{\n{source}\n}}\n"

import os
import re


def pascal_case_to_snake_case(name: str) -> str:
    """Convert a PascalCase/CamelCase identifier into snake_case."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def pascal_case_to_kebab_case(name: str) -> str:
    """Convert a PascalCase/CamelCase identifier into kebab-case."""
    return pascal_case_to_snake_case(name).replace("_", "-")


def tag_name_to_template_filename(tag_name: str) -> str:
    """Convert a component tag name (e.g. ButtonGroup) into its template filename (button_group.html)."""
    return f"{pascal_case_to_snake_case(tag_name)}.html"


def normalize_path_separators(path: str) -> str:
    """Normalize Windows path separators to forward slashes for consistent template paths."""
    return path.replace("\\", "/")


def extract_tag_name_from_raw(raw_tag: str) -> str:
    """
    Extract the tag name from a raw HTML start tag string.

    Example:
        raw_tag='<Button text="OK"/>' -> 'Button'
    """
    match = re.search(r"<\s*([A-Za-z][A-Za-z0-9]*)", raw_tag)
    return match.group(1) if match else ""


def detect_root_directory(
    start_directory: str | None = None,
    project_markers: list[str] | None = None,
) -> str:
    """
    Walk upward from `start_directory` (or CWD) until a directory containing a project marker is found.

    If no marker is found, returns the start directory.
    """
    current_dir = start_directory or os.getcwd()
    markers = project_markers or [
        "pyproject.toml",
        "main.py",
        "README.md",
        ".git",
        ".gitignore",
        "package.json",
        "uv.lock",
        ".venv",
    ]

    search_dir = current_dir
    while search_dir != os.path.dirname(search_dir):
        for marker in markers:
            if os.path.exists(os.path.join(search_dir, marker)):
                return search_dir
        search_dir = os.path.dirname(search_dir)

    return current_dir

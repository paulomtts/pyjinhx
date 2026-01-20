import os
import re


def pascal_case_to_snake_case(name: str) -> str:
    """
    Convert a PascalCase/CamelCase identifier into snake_case.

    Args:
        name: The identifier to convert.

    Returns:
        The snake_case version of the identifier.
    """
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def pascal_case_to_kebab_case(name: str) -> str:
    """
    Convert a PascalCase/CamelCase identifier into kebab-case.

    Args:
        name: The identifier to convert.

    Returns:
        The kebab-case version of the identifier.
    """
    return pascal_case_to_snake_case(name).replace("_", "-")


def tag_name_to_template_filenames(
    tag_name: str, *, extensions: tuple[str, ...] = (".html", ".jinja")
) -> list[str]:
    """
    Convert a component tag name into candidate template filenames.

    Args:
        tag_name: The PascalCase component tag name (e.g., "ButtonGroup").
        extensions: File extensions to use, in order of preference.

    Returns:
        List of candidate filenames (e.g., ["button_group.html", "button_group.jinja"]).
    """
    snake_name = pascal_case_to_snake_case(tag_name)
    return [f"{snake_name}{extension}" for extension in extensions]


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

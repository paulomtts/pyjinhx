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

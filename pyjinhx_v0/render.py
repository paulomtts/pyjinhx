"""Render module: Jinja Environment initialization with project-root detection."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

MARKER_LIST = [
    "pyproject.toml",
    "main.py",
    ".git",
    ".gitignore",
    "package.json",
    "uv.lock",
]


def _detect_project_root(start_dir: str | Path | None = None) -> Path:
    """
    Walk upward from start_dir probing marker list in order.

    Args:
        start_dir: Directory to start walk from. Default: current working directory.

    Returns:
        Path to topmost directory containing any marker; start_dir if no marker found.
    """
    if start_dir is None:
        start_dir = Path.cwd()
    else:
        start_dir = Path(start_dir)

    current = start_dir.resolve()
    last_with_marker = None

    # Walk upward until we reach the root
    while True:
        for marker in MARKER_LIST:
            if (current / marker).exists():
                last_with_marker = current
                break

        # Move to parent directory
        parent = current.parent
        if parent == current:
            # Reached filesystem root
            break
        current = parent

    # Return topmost marker found, or start directory if none
    if last_with_marker is not None:
        return last_with_marker
    return start_dir.resolve()


def _get_or_create_default_environment() -> Environment:
    """
    Create default Jinja Environment with FileSystemLoader at project root.

    Returns:
        Environment configured with FileSystemLoader(detected_root) and autoescape=True.
    """
    root = _detect_project_root()
    return Environment(
        loader=FileSystemLoader(str(root)),
        autoescape=True,
    )


# Initialize default environment at module import time
_default_environment: Environment | None = _get_or_create_default_environment()


def set_default_environment(env: Environment) -> None:
    """
    Override the default Jinja Environment with a custom one.

    Args:
        env: Environment with FileSystemLoader.

    Raises:
        TypeError: If env does not use FileSystemLoader.
    """
    global _default_environment

    if not isinstance(env.loader, FileSystemLoader):
        raise TypeError(
            f"Environment must use FileSystemLoader, got {type(env.loader).__name__}"
        )

    _default_environment = env


def get_loader_root(env: Environment | None = None) -> Path:
    """
    Read the FileSystemLoader root path from an Environment.

    Args:
        env: Environment to inspect. If None, uses default environment.

    Returns:
        Path to the FileSystemLoader root.

    Raises:
        TypeError: If loader is not FileSystemLoader.
    """
    if env is None:
        env = _default_environment

    if not isinstance(env.loader, FileSystemLoader):
        raise TypeError(
            f"Environment must use FileSystemLoader, got {type(env.loader).__name__}"
        )

    # FileSystemLoader.searchpath is a list of search paths
    # For single-root loaders, the first (and usually only) path is the root
    if env.loader.searchpath:
        return Path(env.loader.searchpath[0])

    raise ValueError("FileSystemLoader has no search paths configured")

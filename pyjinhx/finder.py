import inspect
import os
from dataclasses import dataclass, field

from jinja2 import FileSystemLoader

from .utils import (
    normalize_path_separators,
    pascal_case_to_snake_case,
    tag_name_to_template_filename,
)


@dataclass
class Finder:
    """
    Find files under a root directory.

    This centralizes the template discovery logic.

    Results are cached per instance to avoid repeated directory walks.
    """

    root: str
    _index: dict[str, str] = field(default_factory=dict, init=False)
    _is_indexed: bool = field(default=False, init=False)

    def _build_index(self) -> None:
        if self._is_indexed:
            return

        for current_root, dir_names, file_names in os.walk(self.root):
            dir_names.sort()
            file_names.sort()
            for file_name in file_names:
                self._index.setdefault(file_name, os.path.join(current_root, file_name))

        self._is_indexed = True

    def find(self, filename: str) -> str:
        """
        Return the full path to the first file named `filename` found under `root`.

        Raises:
            FileNotFoundError: if the file cannot be found under root.
        """
        self._build_index()
        found_path = self._index.get(filename)
        if found_path is None:
            raise FileNotFoundError(f"Template not found: {filename} under {self.root}")
        return found_path

    def find_template_for_tag(self, tag_name: str) -> str:
        """
        Resolve a PascalCase component tag name to the corresponding template path.

        Example:
            tag_name="ButtonGroup" -> find("button_group.html")
        """
        return self.find(tag_name_to_template_filename(tag_name))

    @staticmethod
    def get_loader_root(loader: FileSystemLoader) -> str:
        """
        Return the first search root from a Jinja `FileSystemLoader`.

        Jinja allows `searchpath` to be a string or a list of strings; PyJinHx uses the first entry.
        """
        search_path = loader.searchpath
        if isinstance(search_path, list):
            return search_path[0]
        return search_path

    @staticmethod
    def resolve_path(path: str, *, root: str) -> str:
        """
        Resolve `path` into an absolute path.

        If `path` is absolute, it is returned as-is. Otherwise, it is joined onto `root`.
        This is useful for explicit file references (extra HTML/JS) where we do not want to search.
        """
        if os.path.isabs(path):
            return path
        return os.path.join(root, path)

    @staticmethod
    def detect_root_directory(
        *,
        start_directory: str | None = None,
        project_markers: list[str] | None = None,
    ) -> str:
        """
        Walk upward from `start_directory` (or CWD) until a directory containing a project marker is found.

        If no marker is found, returns the start directory.
        """
        current_dir = start_directory or os.getcwd()
        markers = project_markers or ["pyproject.toml", "main.py", "README.md", ".git"]

        search_dir = current_dir
        while search_dir != os.path.dirname(search_dir):
            for marker in markers:
                if os.path.exists(os.path.join(search_dir, marker)):
                    return search_dir
            search_dir = os.path.dirname(search_dir)

        return current_dir

    @staticmethod
    def get_class_directory(component_class: type) -> str:
        """Return the directory containing the given class' source file, with normalized separators.

        Example:
            component_class=Button -> /app/components/ui/button.py
        """
        return normalize_path_separators(
            os.path.dirname(inspect.getfile(component_class))
        )

    @staticmethod
    def get_relative_template_path(
        component_dir: str, search_root: str, component_name: str
    ) -> str:
        """
        Compute the template path relative to the Jinja loader root.

        Example: component_dir=/app/components/ui, search_root=/app, component_name=Button
        -> components/ui/button.html
        """
        relative_dir = normalize_path_separators(
            os.path.relpath(component_dir, search_root)
        )
        filename = f"{pascal_case_to_snake_case(component_name)}.html"
        return f"{relative_dir}/{filename}"

    @staticmethod
    def find_in_directory(directory: str, filename: str) -> str | None:
        """
        Return the path to `filename` inside `directory` if it exists; otherwise return None.

        This is meant for component-adjacent assets (e.g. auto-discovered JS files) where we do not
        want to walk/search a root directory.
        """
        candidate_path = os.path.join(directory, filename)
        if os.path.exists(candidate_path):
            return candidate_path
        return None

import inspect
import os
from dataclasses import dataclass, field

from jinja2 import FileSystemLoader

from .utils import (
    detect_root_directory,
    normalize_path_separators,
    pascal_case_to_snake_case,
    tag_name_to_template_filenames,
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

    # ---------
    # Helpers
    # ---------

    def _build_index(self) -> None:
        if self._is_indexed:
            return

        for current_root, dir_names, file_names in os.walk(self.root):
            dir_names.sort()
            file_names.sort()
            for file_name in file_names:
                self._index.setdefault(file_name, os.path.join(current_root, file_name))

        self._is_indexed = True

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
    def detect_root_directory(
        start_directory: str | None = None,
        project_markers: list[str] | None = None,
    ) -> str:
        return detect_root_directory(
            start_directory=start_directory,
            project_markers=project_markers,
        )

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
    def get_relative_template_paths(
        component_dir: str,
        search_root: str,
        component_name: str,
        *,
        extensions: tuple[str, ...] = (".html", ".jinja"),
    ) -> list[str]:
        """
        Compute candidate template paths relative to the Jinja loader root.

        Order matters: earlier entries are preferred during auto-lookup.
        """
        relative_dir = normalize_path_separators(
            os.path.relpath(component_dir, search_root)
        )
        snake_name = pascal_case_to_snake_case(component_name)
        return [f"{relative_dir}/{snake_name}{extension}" for extension in extensions]

    # ------------------
    # Public instance API
    # ------------------

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
        last_error: FileNotFoundError | None = None
        for candidate_filename in tag_name_to_template_filenames(tag_name):
            try:
                return self.find(candidate_filename)
            except FileNotFoundError as exc:
                last_error = exc
        if last_error is None:
            raise FileNotFoundError(
                f"Template not found for tag: {tag_name} under {self.root}"
            )
        raise last_error

    def collect_javascript_files(self, relative_to_root: bool = False) -> list[str]:
        """
        Collect all JavaScript files under `root`.

        Args:
            relative_to_root: If True, return paths relative to `root` (useful for building static file lists).
                              If False, return absolute paths.

        Returns:
            A deterministic, sorted list of `.js` file paths (directories and file names are walked in sorted order).
        """
        javascript_files: list[str] = []

        if not os.path.exists(self.root):
            return javascript_files

        for current_root, dir_names, file_names in os.walk(self.root):
            dir_names.sort()
            file_names.sort()
            for file_name in file_names:
                if not file_name.lower().endswith(".js"):
                    continue
                full_path = os.path.join(current_root, file_name)
                if relative_to_root:
                    javascript_files.append(
                        normalize_path_separators(os.path.relpath(full_path, self.root))
                    )
                else:
                    javascript_files.append(normalize_path_separators(full_path))

        return javascript_files

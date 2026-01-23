import inspect
import os
from dataclasses import dataclass, field

from jinja2 import FileSystemLoader

from .utils import (
    detect_root_directory,
    normalize_path_separators,
    pascal_case_to_kebab_case,
    pascal_case_to_snake_case,
    tag_name_to_template_filenames,
)


@dataclass
class Finder:
    """
    Find files under a root directory.

    Centralizes template discovery logic with caching to avoid repeated directory walks.

    Attributes:
        root: The root directory to search within.
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

    @staticmethod
    def get_loader_root(loader: FileSystemLoader) -> str:
        """
        Return the first search root from a Jinja FileSystemLoader.

        Jinja allows searchpath to be a string or a list of strings; PyJinHx uses the first entry.

        Args:
            loader: The Jinja FileSystemLoader to extract the root from.

        Returns:
            The first search path directory.
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
        """
        Find the project root by walking upward from a starting directory until a marker file is found.

        Args:
            start_directory: Directory to start searching from. Defaults to current working directory.
            project_markers: Files/directories indicating project root (e.g., "pyproject.toml", ".git").

        Returns:
            The detected project root directory, or the start directory if no marker is found.
        """
        return detect_root_directory(
            start_directory=start_directory,
            project_markers=project_markers,
        )

    @staticmethod
    def find_in_directory(directory: str, filename: str) -> str | None:
        """
        Check if a file exists directly in a directory (no recursive search).

        Useful for component-adjacent assets (e.g., auto-discovered JS files).

        Args:
            directory: The directory to check.
            filename: The filename to look for.

        Returns:
            The full path to the file if it exists, or None otherwise.
        """
        candidate_path = os.path.join(directory, filename)
        if os.path.exists(candidate_path):
            return candidate_path
        return None

    @staticmethod
    def get_class_directory(component_class: type) -> str:
        """
        Return the directory containing the given class's source file.

        Args:
            component_class: The class to locate.

        Returns:
            The directory path with normalized separators.

        Example:
            >>> Finder.get_class_directory(Button)
            '/app/components/ui'
        """
        return normalize_path_separators(
            os.path.dirname(inspect.getfile(component_class))
        )

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

        Args:
            component_dir: Absolute path to the component's directory.
            search_root: The Jinja loader's root directory.
            component_name: The PascalCase component name.
            extensions: File extensions to try, in order of preference.

        Returns:
            List of relative template paths to try during auto-lookup.
        """
        relative_dir = normalize_path_separators(
            os.path.relpath(component_dir, search_root)
        )
        snake_name = pascal_case_to_snake_case(component_name)
        kebab_name = pascal_case_to_kebab_case(component_name)
        candidates = []
        for extension in extensions:
            candidates.append(f"{relative_dir}/{snake_name}{extension}")
            candidates.append(f"{relative_dir}/{kebab_name}{extension}")
        return candidates

    def find(self, filename: str) -> str:
        """
        Find a file by name under the root directory.

        Args:
            filename: The filename to search for.

        Returns:
            The full path to the first matching file.

        Raises:
            FileNotFoundError: If the file cannot be found under root.
        """
        self._build_index()
        found_path = self._index.get(filename)
        if found_path is None:
            raise FileNotFoundError(f"Template not found: {filename} under {self.root}")
        return found_path

    def find_template_for_tag(self, tag_name: str) -> str:
        """
        Resolve a PascalCase component tag name to its template path.

        Tries multiple extensions (.html, .jinja) in order of preference.

        Args:
            tag_name: The PascalCase component tag name (e.g., "ButtonGroup").

        Returns:
            The full path to the template file.

        Raises:
            FileNotFoundError: If no matching template is found.

        Example:
            >>> finder.find_template_for_tag("ButtonGroup")
            '/app/components/button_group.html'
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

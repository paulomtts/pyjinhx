# Finder

File discovery engine for templates, JavaScript, and CSS assets.

## Class

### Finder

Centralizes template and asset discovery with caching to avoid repeated directory walks.

#### Constructor

```python
Finder(root: str)
```

**Parameters:**
- `root` (str): The root directory to search within.

#### Instance Methods

##### find()

```python
def find(filename: str) -> str
```

Find a file by name under the root directory.

**Parameters:**
- `filename` (str): The filename to search for.

**Returns:** The full path to the first matching file.

**Raises:** `FileNotFoundError` if the file is not found.

##### find_template_for_tag()

```python
def find_template_for_tag(tag_name: str) -> str
```

Resolve a PascalCase tag name to its template file path. Tries candidates in order: `snake_case.html`, `kebab-case.html`, `snake_case.jinja`, `kebab-case.jinja`.

**Parameters:**
- `tag_name` (str): The PascalCase component name (e.g., `"ButtonGroup"`).

**Returns:** The full path to the template file.

**Raises:** `FileNotFoundError` if no matching template is found.

##### collect_javascript_files()

```python
def collect_javascript_files(relative_to_root: bool = False) -> list[str]
```

Collect all `.js` files under `root`.

**Parameters:**
- `relative_to_root` (bool): If True, return paths relative to `root`. If False (default), return absolute paths.

**Returns:** A sorted list of JavaScript file paths.

##### collect_css_files()

```python
def collect_css_files(relative_to_root: bool = False) -> list[str]
```

Collect all `.css` files under `root`.

**Parameters:**
- `relative_to_root` (bool): If True, return paths relative to `root`. If False (default), return absolute paths.

**Returns:** A sorted list of CSS file paths.

#### Static Methods

##### get_class_directory()

```python
@staticmethod
def get_class_directory(component_class: type) -> str
```

Return the directory containing the given class's source file.

**Parameters:**
- `component_class` (type): The class to locate.

**Returns:** The directory path.

##### get_relative_template_paths()

```python
@staticmethod
def get_relative_template_paths(
    component_dir: str,
    search_root: str,
    component_name: str,
    *,
    extensions: tuple[str, ...] = (".html", ".jinja"),
) -> list[str]
```

Compute candidate template paths relative to the Jinja loader root. Generates both snake_case and kebab-case variants for each extension.

**Parameters:**
- `component_dir` (str): Absolute path to the component's directory.
- `search_root` (str): The Jinja loader's root directory.
- `component_name` (str): The PascalCase component name.
- `extensions` (tuple[str, ...]): File extensions to try.

**Returns:** List of relative template paths to try.

##### find_in_directory()

```python
@staticmethod
def find_in_directory(directory: str, filename: str) -> str | None
```

Check if a file exists directly in a directory (non-recursive).

**Parameters:**
- `directory` (str): The directory to check.
- `filename` (str): The filename to look for.

**Returns:** The full path if found, or `None`.

##### get_loader_root()

```python
@staticmethod
def get_loader_root(loader: FileSystemLoader) -> str
```

Return the first search path from a Jinja `FileSystemLoader`.

**Parameters:**
- `loader` (FileSystemLoader): The loader to extract the root from.

**Returns:** The first search path directory.

##### detect_root_directory()

```python
@staticmethod
def detect_root_directory(
    start_directory: str | None = None,
    project_markers: list[str] | None = None,
) -> str
```

Find the project root by walking upward until a marker file is found.

**Parameters:**
- `start_directory` (str | None): Directory to start from. Defaults to current working directory.
- `project_markers` (list[str] | None): Marker files to look for. Defaults to common markers (`pyproject.toml`, `.git`, etc.).

**Returns:** The detected project root directory, or the start directory if no marker is found.

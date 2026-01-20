# Utilities

Helper functions used internally by PyJinHx.

## Overview

These utility functions handle name conversion, path normalization, and project detection. While primarily used internally, they can be useful for advanced use cases.

## API Reference

::: pyjinhx.utils.pascal_case_to_snake_case
    options:
      show_root_heading: true
      heading_level: 3

::: pyjinhx.utils.pascal_case_to_kebab_case
    options:
      show_root_heading: true
      heading_level: 3

::: pyjinhx.utils.tag_name_to_template_filenames
    options:
      show_root_heading: true
      heading_level: 3

::: pyjinhx.utils.normalize_path_separators
    options:
      show_root_heading: true
      heading_level: 3

::: pyjinhx.utils.extract_tag_name_from_raw
    options:
      show_root_heading: true
      heading_level: 3

::: pyjinhx.utils.detect_root_directory
    options:
      show_root_heading: true
      heading_level: 3

## Usage Examples

### Name Conversions

```python
from pyjinhx.utils import (
    pascal_case_to_snake_case,
    pascal_case_to_kebab_case,
)

# PascalCase to snake_case (for templates)
pascal_case_to_snake_case("ButtonGroup")  # "button_group"
pascal_case_to_snake_case("MyWidget")     # "my_widget"

# PascalCase to kebab-case (for JavaScript files)
pascal_case_to_kebab_case("ButtonGroup")  # "button-group"
pascal_case_to_kebab_case("MyWidget")     # "my-widget"
```

### Template Filename Generation

```python
from pyjinhx.utils import tag_name_to_template_filenames

# Default extensions
tag_name_to_template_filenames("ButtonGroup")
# ["button_group.html", "button_group.jinja"]

# Custom extensions
tag_name_to_template_filenames("ButtonGroup", extensions=(".html.j2",))
# ["button_group.html.j2"]
```

### Path Normalization

```python
from pyjinhx.utils import normalize_path_separators

# Windows paths to forward slashes
normalize_path_separators("components\\ui\\button.html")
# "components/ui/button.html"
```

### Tag Extraction

```python
from pyjinhx.utils import extract_tag_name_from_raw

extract_tag_name_from_raw('<Button text="OK"/>')  # "Button"
extract_tag_name_from_raw('<  MyWidget >')        # "MyWidget"
extract_tag_name_from_raw('<div class="x">')      # "div"
```

### Project Root Detection

```python
from pyjinhx.utils import detect_root_directory

# From current directory
root = detect_root_directory()

# From specific start point
root = detect_root_directory(start_directory="/path/to/subdir")

# With custom markers
root = detect_root_directory(
    project_markers=["setup.py", "pyproject.toml", "Makefile"]
)
```

## Name Conversion Table

| Class Name | snake_case | kebab-case |
|------------|------------|------------|
| `Button` | `button` | `button` |
| `ActionButton` | `action_button` | `action-button` |
| `MyCustomWidget` | `my_custom_widget` | `my-custom-widget` |
| `HTMLParser` | `h_t_m_l_parser` | `h-t-m-l-parser` |

## Default Project Markers

When auto-detecting project root, these files/directories are checked:

- `pyproject.toml`
- `main.py`
- `README.md`
- `.git`
- `.gitignore`
- `package.json`
- `uv.lock`
- `.venv`

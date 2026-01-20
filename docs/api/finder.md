# Finder

File discovery utilities for templates and assets.

## Overview

The `Finder` class provides methods for locating templates and other files within a directory tree. Results are cached to avoid repeated directory walks.

## API Reference

::: pyjinhx.Finder
    options:
      members:
        - find
        - find_template_for_tag
        - collect_javascript_files
        - get_loader_root
        - detect_root_directory
        - find_in_directory
        - get_class_directory
        - get_relative_template_path
        - get_relative_template_paths
      show_root_heading: true
      heading_level: 3

## Usage Examples

### Finding Templates

```python
from pyjinhx import Finder

finder = Finder(root="./components")

# Find by exact filename
path = finder.find("button.html")
# Returns: "/app/components/ui/button.html"

# Find template for a component tag
path = finder.find_template_for_tag("ButtonGroup")
# Looks for: button_group.html, button_group.jinja
```

### Collecting JavaScript Files

```python
finder = Finder(root="./components")

# Get absolute paths
js_files = finder.collect_javascript_files()
# ['/app/components/ui/button.js', '/app/components/ui/dropdown.js']

# Get relative paths
js_files = finder.collect_javascript_files(relative_to_root=True)
# ['ui/button.js', 'ui/dropdown.js']
```

### Project Root Detection

```python
from pyjinhx import Finder

# Auto-detect from current directory
root = Finder.detect_root_directory()

# Start from specific directory
root = Finder.detect_root_directory(start_directory="/path/to/start")

# Custom markers
root = Finder.detect_root_directory(
    project_markers=["setup.py", "Makefile"]
)
```

### Working with Jinja Loaders

```python
from jinja2 import FileSystemLoader
from pyjinhx import Finder

loader = FileSystemLoader(["./templates", "./components"])
root = Finder.get_loader_root(loader)
# Returns: "./templates" (first entry)
```

### Component Directory Utilities

```python
from pyjinhx import Finder
from components.ui.button import Button

# Get directory containing a class
dir_path = Finder.get_class_directory(Button)
# "/app/components/ui"

# Get relative template path
rel_path = Finder.get_relative_template_path(
    component_dir="/app/components/ui",
    search_root="/app",
    component_name="Button"
)
# "components/ui/button.html"
```

## Caching

The `Finder` caches its directory index on first use:

```python
finder = Finder(root="./components")

# First call builds the index
finder.find("button.html")  # Walks directory tree

# Subsequent calls use cache
finder.find("card.html")  # Instant lookup
finder.find("modal.html")  # Instant lookup
```

Each `Finder` instance has its own cache. The `Renderer` caches `Finder` instances per root directory.

## Template Extensions

Templates are searched with these extensions in order:

1. `.html`
2. `.jinja`

```python
# Finds button.html or button.jinja
path = finder.find_template_for_tag("Button")
```

"""The todo panel: a classless shell whose children are nested as tags.

The factory call needs an explicit template_dir because it runs at import
time, before setup() has told discovery where the components root is.
"""

from pathlib import Path

from pyjinhx.classless import component

App = component("App", template_dir=Path(__file__).parent)

__all__ = ["App"]

"""Importing the package imports the one module that is plain Python.

``setup()`` imports only the documents that hold a ``{#python`` block, so a
``.py`` subclass of one is registered only when something imports it.
"""

from tests.fixtures.fewer_files.pjx_python.ui.pages.home.todos import todo_name_fields

__all__ = ["todo_name_fields"]

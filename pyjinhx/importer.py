"""Import a ``.pjx`` document that holds a ``{#python`` block as a module.

A finder at the end of ``sys.meta_path`` answers for ``<package>/<name>.pjx``
once every ordinary finder has failed, so a normal import never reaches it.
The loader runs the block as the module body, compiled from the padded source
(`sfc.python_source`) so tracebacks and ``inspect`` name the file's own lines.

Stdlib-only at module scope: ``import pyjinhx`` installs the finder and must
not pull in pydantic or jinja2.
"""

import importlib.abc
import importlib.util
import os
import re
import sys
import threading
from collections.abc import Sequence
from pathlib import Path
from types import CodeType, ModuleType
from typing import NoReturn

from pyjinhx.sfc import python_block, python_source

# A line that opens a block, or that opens one the v0.x way. The finder only
# sniffs: a malformed block is the loader's error, so a probe such as
# `importlib.util.find_spec` or a `try: import x` never trips over a bad file.
_OPENER_RE = re.compile(r"^\{#[ \t]?python", re.MULTILINE)

# What v0.x wrote; in v2 it is prose, so without a message the import would
# fail with a bare ModuleNotFoundError.
_V0_OPENER_RE = re.compile(r"\{#[ \t]+python[ \t\r]*(\n|\Z)")

# Each loaded document's module name and class, by resolved file path.
_documents: dict[Path, tuple[str, type]] = {}
_documents_lock = threading.Lock()


def _module_file(name: str) -> Path | None:
    """The resolved file of the loaded module ``name``, if it has one."""
    file = getattr(sys.modules.get(name), "__file__", None)
    return Path(file).resolve() if file else None


def first_line(cls: type) -> int:
    """The line of ``cls``'s ``class`` statement, which is the file's own line."""
    return getattr(cls, "__firstlineno__", 0)


def loaded_document(path: str | Path) -> tuple[str, type] | None:
    """The module name and document class of the ``.pjx`` at ``path``, if that
    file was imported through the hook and its module is still loaded."""
    resolved = Path(path).resolve()
    with _documents_lock:
        found = _documents.get(resolved)
    return found if found and _module_file(found[0]) == resolved else None


class PjxLoader(importlib.abc.SourceLoader):
    """Run the ``{#python`` block of one ``.pjx`` file as a module body.

    No bytecode is cached: `get_code` compiles the block every time.
    """

    def __init__(self, fullname: str, path: str) -> None:
        self.name = fullname
        self.path = path

    def get_filename(self, fullname: str) -> str:
        return self.path

    def get_data(self, path: str) -> bytes:
        return Path(path).read_bytes()

    def is_package(self, fullname: str) -> bool:
        return False

    def get_source(self, fullname: str) -> str:
        """The padded Python of the block, as `sfc.python_source` gives it.

        Raises:
            ImportError: The file opens with the v0.x ``{# python``, or has no
                block.
            SyntaxError: The block is malformed.
        """
        text = self.get_data(self.path).decode("utf-8-sig")
        source = python_source(text, self.path)
        if source is None:
            hint = (
                "; it opens with `{# python`, remove the space to write `{#python`"
                if _V0_OPENER_RE.match(text)
                else ""
            )
            raise ImportError(
                f"{self.path} has no {{#python block{hint}",
                name=self.name,
                path=self.path,
            )
        return source

    def get_code(self, fullname: str) -> CodeType:
        return compile(self.get_source(fullname), self.path, "exec", dont_inherit=True)

    def exec_module(self, module: ModuleType) -> None:
        """Run the block, then refuse a document whose classes do not fit it.

        Raises:
            ImportError: The file is already loaded under another module name,
                or no class, or two, are named for the file.
        """
        resolved = Path(self.path).resolve()
        with _documents_lock:
            first = _documents.get(resolved)
        if first and first[0] != self.name and _module_file(first[0]) == resolved:
            self._refuse(1, f"already imported as {first[0]!r}; one file is one module")
        super().exec_module(module)
        document = self._document_class(module)
        with _documents_lock:
            _documents[resolved] = (self.name, document)

    def _document_class(self, module: ModuleType) -> type:
        """The component class the document's markup belongs to: the one defined
        in the block whose snake_case name is the file's stem.

        Raises:
            ImportError: There is none, or there are two.
        """
        from pyjinhx._component import BaseComponent, _pascal_to_snake

        stem = self.name.rpartition(".")[2]
        named = sorted(
            {
                value
                for value in vars(module).values()
                if isinstance(value, type)
                and issubclass(value, BaseComponent)
                and value.__module__ == self.name
                and _pascal_to_snake(value.__name__) == stem
            },
            key=first_line,
        )
        if not named:
            block = python_block(
                self.get_data(self.path).decode("utf-8-sig"), self.path
            )
            self._refuse(
                block.open_line if block else 1,
                f"no component class is named for {stem!r}; the block must "
                f"define the class whose snake_case name is the file's stem",
            )
        if len(named) > 1:
            names = " and ".join(cls.__name__ for cls in named)
            self._refuse(
                first_line(named[1]),
                f"{names} are both named for {stem!r}; keep one",
            )
        return named[0]

    def _refuse(self, line: int, message: str) -> NoReturn:
        raise ImportError(
            f"{self.path}:{line}: {message}", name=self.name, path=self.path
        )


class PjxFinder(importlib.abc.MetaPathFinder):
    """Find ``<last segment>.pjx`` on the search path, if it opens a block."""

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ):
        filename = fullname.rpartition(".")[2] + ".pjx"
        for entry in sys.path if path is None else path:
            if not isinstance(entry, str):
                continue
            candidate = Path(entry or os.getcwd()) / filename
            try:
                text = candidate.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                continue
            if _OPENER_RE.search(text):
                return importlib.util.spec_from_file_location(
                    fullname, candidate, loader=PjxLoader(fullname, str(candidate))
                )
        return None


def _is_finder(finder: object) -> bool:
    """Whether ``finder`` is ours, matched by name so that a reloaded module's
    new class still recognises the instance the old one installed."""
    return type(finder).__name__ == "PjxFinder"


def install() -> None:
    """Append the finder to ``sys.meta_path`` unless it is already there."""
    if not any(_is_finder(finder) for finder in sys.meta_path):
        sys.meta_path.append(PjxFinder())


def uninstall() -> None:
    """Remove the finder from ``sys.meta_path``."""
    sys.meta_path[:] = [f for f in sys.meta_path if not _is_finder(f)]

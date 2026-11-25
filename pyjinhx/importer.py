"""Import a ``.pjx`` document that holds a ``{#python`` block as a module.

A finder at the end of ``sys.meta_path`` answers for ``<package>/<name>.pjx``
once every ordinary finder has failed, so a normal import never reaches it.
The loader runs the block as the module body, compiled from the padded source
(`sfc.python_source`) so tracebacks and ``inspect`` name the file's own lines.

Stdlib-only at module scope: ``import pyjinhx`` installs the finder and must
not pull in pydantic or jinja2.
"""

import importlib
import importlib.util
import os
import sys
import threading
from collections.abc import Sequence
from pathlib import Path
from importlib.machinery import ModuleSpec
from types import CodeType, ModuleType
from typing import NoReturn

from pyjinhx.sfc import module_name_for, opener_line, python_block, python_source

# Each loaded document's module name and class, by resolved file path.
_documents: dict[Path, tuple[str, type]] = {}
_documents_lock = threading.Lock()

# The hash of each loaded document's block body, by resolved file path.
_bodies: dict[Path, int] = {}
# The hash of the changed block body `block_changed` last reported, by path.
_reported: dict[Path, int] = {}


def _body_hash(body: str) -> int:
    """A hash of a block body that does not depend on the file's line ends, which
    reading as text and decoding bytes spell differently."""
    return hash(body.replace("\r\n", "\n"))


def block_changed(path: str | Path, source: str) -> bool:
    """Whether ``source``, the text now in the ``.pjx`` at ``path``, holds a
    block other than the one the hook imported, and this is the first time that
    edit is seen. A file the hook never loaded, or a block that no longer
    parses, is not a change. Any difference in the body counts, a comment or
    whitespace included: the module the process holds is the old text.
    """
    resolved = Path(path).resolve()
    with _documents_lock:
        imported = _bodies.get(resolved)
    if imported is None:
        return False
    try:
        block = python_block(source, str(path))
    except SyntaxError:
        return False
    if block is None:
        return False
    body = _body_hash(block.body)
    with _documents_lock:
        if body == imported:
            _reported.pop(resolved, None)
            return False
        if _reported.get(resolved) == body:
            return False
        _reported[resolved] = body
        return True


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


def import_document(path: str | Path) -> ModuleType:
    """Import the ``.pjx`` document at ``path`` as a module, once.

    A document the hook already loaded is returned as loaded, whatever name it
    was imported under. Otherwise it is imported under the name
    `sfc.module_name_for` derives from ``sys.path``.

    Raises:
        ImportError: No ``sys.path`` entry reaches the file, or the name
            resolves to something else, such as a ``card.py`` or a ``card/``
            directory beside the file. Whatever the block raises passes through.
    """
    loaded = loaded_document(path)
    if loaded is not None:
        return sys.modules[loaded[0]]
    name = module_name_for(path, sys.path)
    if name is None:
        raise ImportError(
            f"{path} cannot be imported: no entry of sys.path holds it under "
            f"directories that are valid names. Add the root of its package to "
            f"sys.path, or put an __init__.py in each directory above it up to "
            f"a directory that is on sys.path. Or import the module before "
            f"setup().",
            path=str(path),
        )
    try:
        module = importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name is None or not name.startswith(error.name):
            raise
        parent = sys.modules.get(name.partition(".")[0])
        found = getattr(parent, "__file__", None) or list(
            getattr(parent, "__path__", [])
        )
        raise ImportError(
            f"{path} is shadowed: importing {name!r} could not find it, because "
            f"{name.partition('.')[0]!r} is {found}. Rename or remove one of the two.",
            name=name,
            path=str(path),
        ) from error
    if _module_file(name) != Path(path).resolve():
        owner = getattr(module, "__file__", None) or list(
            getattr(module, "__path__", [])
        )
        raise ImportError(
            f"{path} is shadowed: importing {name!r} found {owner} instead. "
            f"Rename or remove one of the two.",
            name=name,
            path=str(path),
        )
    return module


def _mark_classes(module: ModuleType) -> None:
    """Tag the components the block defined, so that `all_component_classes`
    drops them once the import is refused or the module is gone."""
    from pyjinhx._component import BaseComponent

    for value in vars(module).values():
        if (
            isinstance(value, type)
            and issubclass(value, BaseComponent)
            and value.__module__ == module.__name__
        ):
            value._pjx_document = True  # pyright: ignore[reportAttributeAccessIssue]


class PjxLoader:
    """Run the ``{#python`` block of one ``.pjx`` file as a module body.

    No bytecode is cached: `get_code` compiles the block every time. A plain
    class, as ``importlib.abc`` costs more to import than the rest of pyjinhx.
    """

    def __init__(self, fullname: str, path: str) -> None:
        self.name = fullname
        self.path = path

    def get_filename(self, fullname: str) -> str:
        return self.path

    def get_data(self, path: str) -> bytes:
        return Path(path).read_bytes()

    def create_module(self, spec: ModuleSpec) -> None:
        """Take the default module."""

    def is_package(self, fullname: str) -> bool:
        return False

    def get_source(self, fullname: str) -> str:
        """The padded Python of the block, as `sfc.python_source` gives it.

        Raises:
            ImportError: The file has no block.
            SyntaxError: The block is malformed.
        """
        text = self.get_data(self.path).decode("utf-8-sig")
        source = python_source(text, self.path)
        if source is None:
            raise ImportError(
                f"{self.path} has no {{#python block", name=self.name, path=self.path
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
        text = self.get_data(self.path).decode("utf-8-sig")
        try:
            exec(self.get_code(self.name), module.__dict__)
        finally:
            _mark_classes(module)
        document = self._document_class(module)
        block = python_block(text, self.path)
        with _documents_lock:
            _documents[resolved] = (self.name, document)
            if block is not None:
                _bodies[resolved] = _body_hash(block.body)
                _reported.pop(resolved, None)

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


class PjxFinder:
    """Find ``<last segment>.pjx`` on the search path, if it opens a block."""

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        filename = fullname.rpartition(".")[2] + ".pjx"
        for entry in sys.path if path is None else path:
            if not isinstance(entry, str):
                continue
            candidate = os.path.join(entry or os.getcwd(), filename)
            if not os.path.isfile(candidate):
                continue
            try:
                text = Path(candidate).read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                continue
            if opener_line(text) is not None:
                return importlib.util.spec_from_file_location(
                    fullname, candidate, loader=PjxLoader(fullname, str(candidate))
                )
        return None

    def invalidate_caches(self) -> None:
        """Nothing is cached."""


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

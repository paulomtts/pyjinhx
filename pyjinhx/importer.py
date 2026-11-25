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
from collections.abc import Sequence
from pathlib import Path
from types import CodeType, ModuleType

from pyjinhx.sfc import python_block, python_source

# What v0.x wrote; in v2 it is prose, so without a message the import would
# fail with a bare ModuleNotFoundError.
_V0_OPENER_RE = re.compile(r"\{#[ \t]+python[ \t\r]*(\n|\Z)")


class PjxLoader(importlib.abc.SourceLoader):
    """Run the ``{#python`` block of one ``.pjx`` file as a module body.

    No bytecode is cached: `SourceLoader` only writes a ``.pyc`` when
    ``path_stats`` answers, and this loader leaves it unanswered.
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
        return self._python(self.get_data(self.path))

    def source_to_code(self, data, path="<string>", *, _optimize=-1) -> CodeType:
        return compile(
            self._python(data), self.path, "exec", dont_inherit=True, optimize=_optimize
        )

    def _python(self, data: bytes | str) -> str:
        """The padded Python of the document ``data``."""
        text = data if isinstance(data, str) else data.decode("utf-8-sig")
        source = python_source(text, self.path)
        if source is None:
            raise ImportError(
                f"{self.path} has no {{#python block", name=self.name, path=self.path
            )
        return source


class PjxFinder(importlib.abc.MetaPathFinder):
    """Find ``<last segment>.pjx`` on the search path, if it holds a block."""

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
            if not candidate.is_file():
                continue
            text = candidate.read_text(encoding="utf-8-sig")
            if python_block(text, str(candidate)) is None:
                if _V0_OPENER_RE.match(text):
                    raise ImportError(
                        f"{candidate} opens with `{{# python`; remove the space "
                        f"to write `{{#python`",
                        name=fullname,
                        path=str(candidate),
                    )
                continue
            return importlib.util.spec_from_file_location(
                fullname, candidate, loader=PjxLoader(fullname, str(candidate))
            )
        return None


def install() -> None:
    """Append the finder to ``sys.meta_path`` unless it is already there."""
    if not any(isinstance(finder, PjxFinder) for finder in sys.meta_path):
        sys.meta_path.append(PjxFinder())


def uninstall() -> None:
    """Remove the finder from ``sys.meta_path``."""
    sys.meta_path[:] = [f for f in sys.meta_path if not isinstance(f, PjxFinder)]

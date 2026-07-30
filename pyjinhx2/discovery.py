"""Discovery — the startup walk that finds .pjx component templates on disk."""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple


class TemplateCandidate(NamedTuple):
    """One `.pjx` file the walk found, and the tag name it would answer to."""

    tag_name: str
    path: Path


_SNAKE_CASE_RE = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")


def _is_candidate_name(stem: str) -> bool:
    """Whether ``stem`` is a filename a component class could have produced.

    The exact shape `component.py`'s `_pascal_to_snake` emits, so every class
    that resolves a template can be found by this walk, and nothing else is —
    ADR 0007 spends one convention, not six.
    """
    return _SNAKE_CASE_RE.fullmatch(stem) is not None


def walk_templates(template_dir: Path | str) -> Iterator[TemplateCandidate]:
    """The `.pjx` files under ``template_dir``, nested ones included, sorted by path.

    Pure over the filesystem: nothing is registered, cached or deduplicated
    here, so the same tree always yields the same sequence and the caller
    decides what to do with collisions. Two files sharing a stem in different
    directories are both yielded — the walk reports what is on disk.
    """
    root = Path(template_dir)
    if not root.is_dir():
        raise NotADirectoryError(
            f"template_dir {str(root)!r} is not a directory, so there is no "
            f"tree to walk for .pjx component templates."
        )
    for path in sorted(root.rglob("*.pjx")):
        if path.is_file() and _is_candidate_name(path.stem):
            yield TemplateCandidate(path.stem, path)

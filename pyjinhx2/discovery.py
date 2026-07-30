"""Discovery — the startup walk that finds .pjx component templates on disk,
and the tag -> class registry built from it.

Two halves with different natures. The walk is pure over the filesystem. The
registry is the process's one mutable name map: assembled complete off to the
side, published in a single locked rebind, and read-only from then on, so no
render ever sees a half-built map. Discovery is the only writer; everyone else
reads through `get_class`, and a miss there is `None`, never an exception.
"""

import re
import threading
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import NamedTuple

from pyjinhx2.component import _pascal_to_snake


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


class _Registry:
    """Holder for the published tag -> class mapping.

    A holder rather than a bare module-level dict: the mapping is replaced
    wholesale on every build, so what module state actually means here is "one
    rebindable reference", and keeping it off the module namespace makes it
    obvious the walk above never touches it.
    """

    __slots__ = ("mapping",)

    def __init__(self) -> None:
        self.mapping: dict[str, type] = {}


_registry = _Registry()
_registry_lock = threading.Lock()


def _tag_for(cls: type) -> str:
    """The tag name ``cls`` answers to — the same snake_case name its template
    is probed under, so a class and its file can never disagree."""
    return _pascal_to_snake(cls.__name__)


def _resolve_tag_owner(tag_name: str, by_tag: Mapping[str, list[type]]) -> type | None:
    """Which class, if any, claims ``tag_name``.

    The single decision point for "who owns this tag", kept apart from the
    swap mechanism so richer answers (duplicate arbitration, explicit
    replacement) can change this without touching how the result is published.
    ``by_tag`` carries every class that resolved to ``tag_name``, not just one,
    so a future duplicate-tag warning has the full collision to inspect rather
    than one this function's caller already discarded. Plain matching here:
    last class in the list wins, mirroring dict-building order. A tag no class
    claims is not an error: an orphan template is a normal thing to find on
    disk.
    """
    candidates = by_tag.get(tag_name)
    return candidates[-1] if candidates else None


def build_registry(template_dir: Path | str, classes: Iterable[type]) -> None:
    """Walk ``template_dir`` and publish a fresh tag -> class registry.

    The new mapping is assembled complete in a local before anything is
    published, so a reader sees either the whole previous registry or the whole
    new one. Raises ``NotADirectoryError`` (from the walk) before any publish
    happens, leaving the live registry untouched.
    """
    by_tag: dict[str, list[type]] = {}
    for cls in classes:
        by_tag.setdefault(_tag_for(cls), []).append(cls)
    fresh: dict[str, type] = {}
    for candidate in walk_templates(template_dir):
        owner = _resolve_tag_owner(candidate.tag_name, by_tag)
        if owner is not None:
            fresh[candidate.tag_name] = owner
    with _registry_lock:
        _registry.mapping = fresh


def get_class(tag_name: str) -> type | None:
    """The component class registered for ``tag_name``, or ``None``.

    Never raises on a miss: the renderer treats an unknown tag as ordinary
    markup and leaves it verbatim, so a miss is an answer, not an error.
    Unlocked — the published mapping is read-only once swapped in.
    """
    return _registry.mapping.get(tag_name)

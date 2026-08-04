"""Discovery — the startup walk that finds .pjx component templates on disk,
and the tag -> class registry built from it.

Two halves with different natures. The walk is pure over the filesystem. The
registry is the process's one mutable name map: assembled complete off to the
side, published in a single locked rebind, and read-only from then on, so no
render ever sees a half-built map. Discovery is the only writer; everyone else
reads through `get_class`, and a miss there is `None`, never an exception.
"""

import logging
import re
import threading
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import NamedTuple

from pyjinhx.component import _pascal_to_snake

logger = logging.getLogger("pyjinhx")


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

    __slots__ = ("mapping", "template_dir")

    def __init__(self) -> None:
        self.mapping: dict[str, type] = {}
        self.template_dir: Path | None = None


_registry = _Registry()
_registry_lock = threading.Lock()


def _tag_for(cls: type) -> str:
    """The tag name ``cls`` answers to — the same snake_case name its template
    is probed under, so a class and its file can never disagree."""
    return _pascal_to_snake(cls.__name__)


def _qualified_name(cls: type) -> str:
    """``cls``'s fully qualified name — the tie-break key for tag collisions.

    Total and stable across runs, unlike the order a caller happens to hand
    its classes over in.
    """
    return f"{cls.__module__}.{cls.__qualname__}"


def _wants_replace(cls: type) -> bool:
    """Whether ``cls`` declared itself the replacement for its tag.

    Read with a default rather than an attribute access so discovery keeps
    working on any class that resolves a tag, including ones that never went
    through `BaseComponent`.
    """
    return bool(getattr(cls, "_pjx_replace", False))


def _resolve_tag_owner(
    tag_name: str, by_tag: Mapping[str, list[type]], warned: set[str]
) -> type | None:
    """Which class, if any, claims ``tag_name``.

    The single decision point for "who owns this tag", kept apart from the
    swap mechanism so richer answers can change this without touching how the
    result is published. ``by_tag`` carries every class that resolved to
    ``tag_name``, not just one, so a collision can be reported in full rather
    than silently narrowed by the caller.

    Two rules decide a collision. A class declared with ``pjx_replace=True``
    has said out loud that it means to take the tag over, so it wins and
    nothing is logged — shadowing a component is a supported move, not a
    mistake to be reported. Otherwise the collision is unintended, and the
    answer must still not depend on the order the caller iterated its classes
    in: candidates are ordered by fully qualified name and the last one
    alphabetically wins — an arbitrary end of a total order, but the same end
    on every run — and a warning names the tag and everyone claiming it.

    Several classes all claiming to be the replacement is itself unintended,
    so those go through the same sort and the same warning, narrowed to the
    competing replacers. ``warned`` keeps warnings to one per tag per build,
    since this runs once per walked template and one stem can sit in two
    directories. A tag no class claims is not an error: an orphan template is
    a normal thing to find on disk.
    """
    candidates = by_tag.get(tag_name)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    replacers = [cls for cls in candidates if _wants_replace(cls)]
    if len(replacers) == 1:
        return replacers[0]
    contenders = replacers or candidates
    ordered = sorted(contenders, key=_qualified_name)
    winner = ordered[-1]
    if tag_name not in warned:
        warned.add(tag_name)
        logger.warning(
            "Duplicate component tag %r claimed by %s; %s wins. Rename all but "
            "one of these classes so each tag has a single owner.",
            tag_name,
            ", ".join(_qualified_name(cls) for cls in ordered),
            _qualified_name(winner),
        )
    return winner


def _has_own_template(cls: type) -> bool:
    """Whether ``cls`` resolved a template of its own on disk.

    The tag a class answers to is decided by the template it already found
    through its MRO (ADR 0007/0010), so a class whose template ships inside an
    installed package can claim its tag without that file having to sit under
    the walked tree. A class with no resolvable template is simply not claimed
    — the same posture as an orphan `.pjx` with no class behind it.
    """
    descriptor = getattr(cls, "__pjx_descriptor__", None)
    path = getattr(descriptor, "template_path", None)
    return isinstance(path, Path) and path.is_file()


def build_registry(template_dir: Path | str | None, classes: Iterable[type]) -> None:
    """Walk ``template_dir`` and publish a fresh tag -> class registry.

    Two sources feed the published mapping: every `.pjx` found by walking
    ``template_dir``, and every offered class that already resolved a template
    of its own on disk (e.g. a builtin shipped inside the installed package,
    nowhere near ``template_dir``). Both funnel into the same tag set and the
    same `_resolve_tag_owner` call, so a tag contested across the two sources
    still gets exactly one collision decision and one warning.

    ``template_dir`` may be ``None`` — no tree to walk; only classes carrying
    their own template claim tags. `get_template_dir()` then reports ``None``
    too, which lets an app with no ``components_root`` of its own still get
    its builtins registered.

    The new mapping is assembled complete in a local before anything is
    published, so a reader sees either the whole previous registry or the whole
    new one. Raises ``NotADirectoryError`` (from the walk) before any publish
    happens, leaving the live registry untouched.
    """
    root = Path(template_dir) if template_dir is not None else None
    offered: list[type] = list(classes)
    by_tag: dict[str, list[type]] = {}
    for cls in offered:
        by_tag.setdefault(_tag_for(cls), []).append(cls)
    fresh: dict[str, type] = {}
    warned: set[str] = set()
    tags: list[str] = (
        [] if root is None else [candidate.tag_name for candidate in walk_templates(root)]
    )
    tags.extend(_tag_for(cls) for cls in offered if _has_own_template(cls))
    for tag_name in dict.fromkeys(tags):
        owner = _resolve_tag_owner(tag_name, by_tag, warned)
        if owner is not None:
            fresh[tag_name] = owner
    with _registry_lock:
        _registry.mapping = fresh
        _registry.template_dir = root


def get_class(tag_name: str) -> type | None:
    """The component class registered for ``tag_name``, or ``None``.

    Never raises on a miss: the renderer treats an unknown tag as ordinary
    markup and leaves it verbatim, so a miss is an answer, not an error.
    Unlocked — the published mapping is read-only once swapped in.
    """
    return _registry.mapping.get(tag_name)


def get_template_dir() -> Path | None:
    """The directory the last successful ``build_registry`` walked, or ``None``.

    The lazy classless factory has no renderer to ask where templates live, and
    the answer discovery already used is the only one that can agree with the
    published mapping.
    """
    return _registry.template_dir


def register_class(tag_name: str, cls: type) -> None:
    """Publish ``cls`` under ``tag_name`` unless the tag already has an owner.

    The one way a tag is claimed after the import-time build, so discovery
    stays the only writer of the mapping. A tag that is already owned is left
    alone: a class registered on demand must never shadow a declared one.
    The mapping is copied and rebound rather than mutated, matching the build,
    so a concurrent reader sees a whole mapping either way.
    The loser is named in a warning rather than dropped silently, since a
    template that never becomes its own component is otherwise invisible.
    """
    with _registry_lock:
        existing = _registry.mapping.get(tag_name)
        if existing is not None:
            logger.warning(
                "Tag %r was built without a class, but %s already declares it; "
                "the declared class keeps the tag and %s is discarded. Give the "
                "classless template a different name if it meant to be its own "
                "component.",
                tag_name,
                _qualified_name(existing),
                _qualified_name(cls),
            )
            return
        _registry.mapping = {**_registry.mapping, tag_name: cls}

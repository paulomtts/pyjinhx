"""Helpers shared by the split test files in this folder."""

import threading
from typing import Annotated

from pyjinhx.components.base import BaseComponent
from pyjinhx.reactive.component import PjxKey, ReactiveComponent
from pyjinhx.reactive.fanout import FanoutCandidate, oob_swaps, walk_manifest
from pyjinhx.reactive.root_attrs import stamp_reactive_root_attrs
from pyjinhx.rendering import registry
from pyjinhx.rendering.segments import RenderedLevel
from pyjinhx.rendering.session import (
    RenderSession,
    current_session,
    get_load_context,
    request_scope,
)

LOAD_CALLS: list[str] = []


GONE_KEYS: set[str] = set()
"""Load keys `FanoutWidget.load()` refuses to build, standing for a region the
server no longer knows about. A failed load is the only thing that makes a
candidate "missing" — a registry miss does not, because the registry is
request-scoped (ADR 0009 E6) and misses for every out-of-primary region."""


class FanoutWidget(ReactiveComponent, react=("todos",)):
    """A reactive component keyed by ``pjx_key``, whose load() is counted."""

    pjx_key: Annotated[str, PjxKey()] = ""
    data: str = ""

    @classmethod
    def load(cls, pjx_key: str) -> "FanoutWidget":
        LOAD_CALLS.append(pjx_key)
        if pjx_key in GONE_KEYS:
            raise LookupError(f"no widget for {pjx_key!r}")
        return cls(pjx_key=pjx_key, data=f"data:{pjx_key}")


class QuietWidget(ReactiveComponent, react=("other",)):
    """A reactive component that no test's dirtied keys ever touch."""


class OwnedWidget(ReactiveComponent, react=("other",)):
    """A nested class that declares itself fully owned by its parent's swap."""

    retain_across_parent_swaps = False


class LoudWidget(ReactiveComponent, react=("todos",)):
    """A reactive component that reacts to the same keys as FanoutWidget but is
    never measured, so a pass mixing it with a too-cheap class must still thread."""

    pjx_key: Annotated[str, PjxKey()] = ""
    data: str = ""

    @classmethod
    def load(cls, pjx_key: str) -> "LoudWidget":
        return cls(pjx_key=pjx_key, data=f"data:{pjx_key}")


CHILD_REGISTERED = threading.Event()
"""Set once NestedChildWidget has rendered and registered under its own id.

NestingParentWidget.load() waits on it so the #1022 ordering under test is the
one the issue reports: the child's *own* top-level build registers first, and
the parent's nested re-render of the same region is the second, colliding
write. Without the gate the two pool workers race and the test would assert on
whichever finished first.
"""


class NestedChildWidget(ReactiveComponent, react=("todos",)):
    """A reactive child that NestingParentWidget's template mounts by tag."""

    pjx_key: Annotated[str, PjxKey()] = ""

    @classmethod
    def load(cls, pjx_key: str) -> "NestedChildWidget":
        LOAD_CALLS.append(f"child:{pjx_key}")
        return cls(pjx_key=pjx_key)


class NestingParentWidget(ReactiveComponent, react=("todos",)):
    """A reactive parent whose template nests NestedChildWidget under a fixed id."""

    pjx_key: Annotated[str, PjxKey()] = ""

    @classmethod
    def load(cls, pjx_key: str) -> "NestingParentWidget":
        LOAD_CALLS.append(f"parent:{pjx_key}")
        CHILD_REGISTERED.wait(timeout=5)
        return cls(pjx_key=pjx_key)


RENDERS: list[str] = []
"""The class name of every component the walk's session finished rendering,
top-level or nested, so a test can tell a skipped build from a run one."""


BOOM_KEYS: set[str] = set()
"""Load keys `HostWidget.load()` fails on with a ValueError, standing for a
loader bug rather than a gone region."""


class HostWidget(ReactiveComponent, react=("todos",)):
    """A reactive parent that mounts NestedChildWidget, with no gate in load()."""

    pjx_key: Annotated[str, PjxKey()] = ""

    @classmethod
    def load(cls, pjx_key: str) -> "HostWidget":
        LOAD_CALLS.append(f"host:{pjx_key}")
        if pjx_key in BOOM_KEYS:
            raise ValueError(f"host loader exploded for {pjx_key!r}")
        if pjx_key in GONE_KEYS:
            raise LookupError(f"no host for {pjx_key!r}")
        return cls(pjx_key=pjx_key)


class HollowHostWidget(ReactiveComponent, react=("todos",)):
    """A reactive region a client may wrongly claim as a parent: it mounts nothing."""

    pjx_key: Annotated[str, PjxKey()] = ""

    @classmethod
    def load(cls, pjx_key: str) -> "HollowHostWidget":
        LOAD_CALLS.append(f"hollow:{pjx_key}")
        return cls(pjx_key=pjx_key)


class OuterWidget(ReactiveComponent, react=("todos",)):
    """The top of a three-level chain: it mounts MiddleWidget."""

    pjx_key: Annotated[str, PjxKey()] = ""

    @classmethod
    def load(cls, pjx_key: str) -> "OuterWidget":
        LOAD_CALLS.append(f"outer:{pjx_key}")
        return cls(pjx_key=pjx_key)


class MiddleWidget(ReactiveComponent, react=("todos",)):
    """The middle of a three-level chain: it mounts NestedChildWidget."""

    pjx_key: Annotated[str, PjxKey()] = ""

    @classmethod
    def load(cls, pjx_key: str) -> "MiddleWidget":
        LOAD_CALLS.append(f"middle:{pjx_key}")
        return cls(pjx_key=pjx_key)


class PreservingHostWidget(ReactiveComponent, react=("todos",)):
    """A parent mounting a dirty child and a disjoint QuietWidget the preserve pass stamps."""

    pjx_key: Annotated[str, PjxKey()] = ""

    @classmethod
    def load(cls, pjx_key: str) -> "PreservingHostWidget":
        LOAD_CALLS.append(f"phost:{pjx_key}")
        return cls(pjx_key=pjx_key)


def _child_registered(component, level, session) -> None:
    """An on_rendered subscriber that releases NestingParentWidget.load()."""
    if isinstance(component, NestedChildWidget):
        CHILD_REGISTERED.set()


def wired_session() -> RenderSession:
    """A session wired the way integrations/fastapi.py:208-210 wires a request's.

    The stamp hook is what writes each rendered root's ``data-pjx-id``, which is
    what `_drop_nested`'s containment check reads; the registry writer is what
    makes the double registration happen at all. The releaser goes last, so it
    only fires once the write it is reporting has landed.
    """
    session = RenderSession()
    session.on_rendered.append(stamp_reactive_root_attrs)
    session.on_rendered.append(registry.register_rendered_instance)
    session.on_rendered.append(_child_registered)
    return session


def _count_render(component, level, session) -> None:
    """An on_rendered subscriber that records each finished render's class name."""
    RENDERS.append(type(component).__name__)


def counting_session() -> RenderSession:
    """`wired_session()` plus the render counter, appended last."""
    session = wired_session()
    session.on_rendered.append(_count_render)
    return session


class PlainWidget(BaseComponent):
    """A discovery-registered component that is NOT a ReactiveComponent.

    A manifest naming a real tag whose class is non-reactive must be dropped by
    the `issubclass` half of `_candidate_class`, not by the unknown-tag half.
    """


SEEN_SESSIONS: list[object] = []
"""What `current_session()` answered inside each SpyWidget.load() call."""


SEEN_LOAD_CONTEXTS: list[object] = []
"""What `get_load_context()` answered inside each SpyWidget.load() call."""


SEEN_THREADS: set[int] = set()
"""The thread each SpyWidget.load() ran on, to prove more than one was used."""


STAT_CALLS: list[str] = []
"""Template paths the loader's freshness closure actually stat()'ed this walk.

Only stats made from inside `uptodate()` are recorded. `get_source()`'s own
initial mtime read and `Path.is_file()`'s probe go through the same
`Path.stat`, and counting those would measure template *loading* rather than
the per-lookup freshness re-check this test is about.
"""


class SpyWidget(ReactiveComponent, react=("todos",)):
    """A reactive component whose load() records its worker's context view."""

    pjx_key: Annotated[str, PjxKey()] = ""
    data: str = ""

    @classmethod
    def load(cls, pjx_key: str) -> "SpyWidget":
        SEEN_SESSIONS.append(current_session())
        SEEN_LOAD_CONTEXTS.append(get_load_context())
        SEEN_THREADS.add(threading.get_ident())
        if pjx_key == "boom":
            raise ValueError("loader exploded")
        return cls(pjx_key=pjx_key, data=f"data:{pjx_key}")


_ABSENT = object()
"""Sentinel for `entry(parent=...)`: distinguishes "no key" from `parent=None`."""


def entry(
    type_name: str,
    instance_id: str,
    load: object = None,
    hash_: str = "h",
    *,
    parent: object = _ABSENT,
) -> dict:
    """Build one synthetic X-PJX-Mounted manifest entry.

    `parent` is added only when passed, so the entry can carry any value,
    including None or a non-string, exactly as a client might send it.
    """
    built: dict = {"type": type_name, "id": instance_id, "load": load, "hash": hash_}
    if parent is not _ABSENT:
        built["parent"] = parent
    return built


def scope():
    """`request_scope()`, kept as a named helper so call sites read the same
    whether or not a future test needs to pass it a pre-built session."""
    return request_scope()


def fresh_hash_for(load: object) -> str:
    """The state hash `walk_manifest`'s dirty path will compute for this load arg.

    Built from an instance shaped exactly like `_build_dirty` builds one, so a
    test can seed a manifest entry with the *matching* hash without hardcoding
    a digest that changes whenever the model's fields do.
    """
    return FanoutWidget(id="probe", pjx_key=str(load), data=f"data:{load}").state_hash()


def candidate(instance_id: str, level=None, resolved=None, status: str = "dirty"):
    """Build one FanoutCandidate carrying only the fields _drop_nested reads."""
    return FanoutCandidate(
        type_name="fanout_widget",
        component_class=FanoutWidget,
        instance_id=instance_id,
        load=None,
        status=status,
        entry=entry("fanout_widget", instance_id),
        resolved=resolved,
        level=level,
    )


def stamped_level(instance_id: str, *children) -> RenderedLevel:
    """A RenderedLevel whose root tag carries data-pjx-id, with children nested."""
    root = f'<div data-pjx-id="{instance_id}">'
    return RenderedLevel(
        segments=[root, *children, "</div>"],
        root_span=(0, len(root)),
        descriptor=FanoutWidget.__pjx_descriptor__,
    )


def _entry(
    entry_id: str, type_name: str, load: str | None, hash_value: str | None = None
):
    """One manifest entry shaped the way `MountedManifest.parse()` emits them."""
    entry: dict[str, object] = {"id": entry_id, "type": type_name, "load": load}
    if hash_value is not None:
        entry["hash"] = hash_value
    return entry


def swaps(manifest, primary_html=None, before=None) -> tuple[str, list[tuple]]:
    """One walk, in its own request, and what it would ship.

    `before` runs inside the request scope ahead of the walk, which is where a
    test seeds the load cache. The cache is per request, so seeding outside
    would be lost. Returns the `oob_swaps` body and each surviving candidate's
    `(instance_id, status, fresh_hash)`, in order.
    """
    session = counting_session()
    with request_scope(session=session):
        if before is not None:
            before()
        candidates = walk_manifest(manifest, {"todos"}, primary_html=primary_html)
        body = str(oob_swaps(candidates, {"todos"}, session))
    return body, [(c.instance_id, c.status, c.fresh_hash) for c in candidates]

"""L2.2.1: per-request accumulation of descriptor CSS/JS paths, deduped by path."""

import threading
from dataclasses import replace
from pathlib import Path

import pytest

from pyjinhx2.component import BaseComponent
from pyjinhx2.descriptor import ClassDescriptor
from pyjinhx2.render import render
from pyjinhx2.session import (
    NoActiveRequestScope,
    RenderSession,
    accumulate_assets,
    request_scope,
)

CSS = Path("/app/components/box.css")
JS = Path("/app/components/box.js")


def _plain_descriptor(owner: type) -> ClassDescriptor:
    """A hand-built descriptor pointed at the shared plain_div.html fixture.

    Bypasses the real MRO/filesystem template walk on purpose (there is no
    `__pjx_template__` override attribute in production code) — same pattern
    test_render_level.py uses.
    """
    return ClassDescriptor(
        template_path=Path("plain_div.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": owner},
    )


class PlainBox(BaseComponent):
    """Component rendered against a hand-built descriptor, not MRO discovery."""


class PlainSibling(BaseComponent):
    """Second class used to prove cross-class dedup on a shared asset path."""


PlainBox.__pjx_descriptor__ = _plain_descriptor(PlainBox)
PlainSibling.__pjx_descriptor__ = _plain_descriptor(PlainSibling)


def with_assets(cls, *, css=(), js=()):
    """Point a class's frozen descriptor at the given asset paths (read-only use)."""
    cls.__pjx_descriptor__ = replace(
        cls.__pjx_descriptor__, css_paths=tuple(css), js_paths=tuple(js)
    )
    return cls


def _accumulating_session() -> RenderSession:
    """A fresh RenderSession with the asset accumulator wired to on_rendered.

    Not entered into a request_scope() by itself: tests bind it explicitly via
    ``request_scope(session=...)`` so the scope and the session under test are
    the same object, matching how accumulate_assets reads current_session().
    """
    template_dir = str(Path(__file__).parent.parent / "templates")
    session = RenderSession(template_dir=template_dir)
    session.on_rendered.append(accumulate_assets)
    return session


def test_accumulates_css_path_from_single_component():
    with_assets(PlainBox, css=[CSS])
    with request_scope(session=_accumulating_session()) as session:
        render(PlainBox(), session)
        assert session.css_assets == {CSS}


def test_accumulates_js_path_from_single_component():
    with_assets(PlainBox, js=[JS])
    with request_scope(session=_accumulating_session()) as session:
        render(PlainBox(), session)
        assert session.js_assets == {JS}


def test_dedups_same_path_across_two_instances_of_same_class():
    with_assets(PlainBox, css=[CSS])
    with request_scope(session=_accumulating_session()) as session:
        render(PlainBox(), session)
        render(PlainBox(), session)
        assert session.css_assets == {CSS}


def test_dedups_same_path_across_two_different_classes_sharing_a_co_located_asset():
    with_assets(PlainBox, css=[CSS])
    with_assets(PlainSibling, css=[CSS])
    with request_scope(session=_accumulating_session()) as session:
        render(PlainBox(), session)
        render(PlainSibling(), session)
        assert session.css_assets == {CSS}


def test_no_op_for_component_with_no_css_or_js_paths():
    with_assets(PlainBox)
    with request_scope(session=_accumulating_session()) as session:
        render(PlainBox(), session)
        assert session.css_assets == set()
        assert session.js_assets == set()


def test_accumulator_resets_between_request_scopes():
    with_assets(PlainBox, css=[CSS])
    with request_scope(session=_accumulating_session()) as first:
        render(PlainBox(), first)
        assert first.css_assets == {CSS}
    with request_scope(session=_accumulating_session()) as second:
        assert second is not first
        assert second.css_assets == set()


def test_two_concurrent_request_scopes_do_not_leak_into_each_other():
    with_assets(PlainBox, css=[CSS])
    with_assets(PlainSibling, css=[Path("/app/components/sibling.css")])
    seen: dict[str, set[Path]] = {}
    started = threading.Barrier(2)

    def run(name, component_cls):
        with request_scope(session=_accumulating_session()) as session:
            started.wait()
            render(component_cls(), session)
            seen[name] = set(session.css_assets)

    threads = [
        threading.Thread(target=run, args=("a", PlainBox)),
        threading.Thread(target=run, args=("b", PlainSibling)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert seen["a"] == {CSS}
    assert seen["b"] == {Path("/app/components/sibling.css")}


def test_on_rendered_fires_once_per_component_not_per_reactive_update():
    with_assets(PlainBox, css=[CSS], js=[JS])
    box = PlainBox()
    with request_scope(session=_accumulating_session()) as session:
        render(box, session)
        render(box, session)
        assert session.css_assets == {CSS}
        assert session.js_assets == {JS}


def test_raises_or_asserts_when_accumulating_outside_active_request_scope():
    with_assets(PlainBox, css=[CSS])
    with pytest.raises(NoActiveRequestScope):
        render(PlainBox(), _accumulating_session())


def test_css_and_js_paths_tracked_distinguishably():
    with_assets(PlainBox, css=[CSS], js=[JS])
    with request_scope(session=_accumulating_session()) as session:
        render(PlainBox(), session)
        assert session.css_assets == {CSS}
        assert session.js_assets == {JS}
        assert CSS not in session.js_assets
        assert JS not in session.css_assets

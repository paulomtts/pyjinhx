"""Composition tests: ReactiveResponse joins the primary body with OOB fragments."""

import dataclasses
from pathlib import Path
from typing import Annotated

import pytest
from markupsafe import Markup

from pyjinhx2 import discovery, registry
from pyjinhx2.reactive.component import PjxKey, ReactiveComponent
from pyjinhx2.reactive.response import ReactiveResponse
from pyjinhx2.session import add_dirtied, request_scope


class ResponseWidget(ReactiveComponent, react=("todos",)):
    """A reactive component keyed by ``pjx_key``, dirtied by the ``todos`` key."""

    pjx_key: Annotated[str, PjxKey()] = ""

    def load(self) -> str:
        return f"data:{self.pjx_key}"


_TEMPLATE_DIR = "templates"
"""Set by `_publish_registry` to this test's tmp_path.

`RenderSession(template_dir="templates")` (the class default) does not exist relative to
the test process's cwd, so every test must enter `scope()` rather than bare
`request_scope()` or the dirty path's `render_level()` raises TemplateNotFound instead of
exercising the code under test.
"""


@pytest.fixture(autouse=True)
def _publish_registry(tmp_path, monkeypatch):
    """Publish a tag -> class map for ResponseWidget and point it at a real template."""
    global _TEMPLATE_DIR
    template = tmp_path / "response_widget.pjx"
    template.write_text("<div>{{ pjx_key }}</div>")
    discovery.build_registry(tmp_path, [ResponseWidget])
    # `_resolve_template_path` probes the class's defining module directory, not the
    # dir passed to build_registry; repoint the descriptor at the tmp_path file, using
    # the bare filename because RenderSession's FileSystemLoader joins names under
    # template_dir and would never open an absolute path.
    ResponseWidget.__pjx_descriptor__ = dataclasses.replace(
        ResponseWidget.__pjx_descriptor__, template_path=Path(template.name)
    )
    _TEMPLATE_DIR = str(tmp_path)
    yield


def scope():
    """`request_scope()` bound to this test's tmp_path template dir."""
    return request_scope(_TEMPLATE_DIR)


def entry(instance_id: str, load: object = None, hash_: str = "stale") -> dict:
    """Build one synthetic X-PJX-Mounted manifest entry for ResponseWidget."""
    return {
        "type": "response_widget",
        "id": instance_id,
        "load": load,
        "hash": hash_,
    }


def test_no_dirtied_and_no_mounted_leaves_primary_untouched():
    with scope():
        response = ReactiveResponse(primary=Markup("<p>hello</p>"))
        assert response.body == Markup("<p>hello</p>")
        assert str(response) == "<p>hello</p>"
        assert response.__html__() == Markup("<p>hello</p>")


def test_dirty_mounted_region_appends_an_oob_fragment_after_the_primary():
    with scope():
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        add_dirtied(["todos"])
        response = ReactiveResponse(
            primary=Markup("<p>hello</p>"), mounted=[entry("a", load="todo-1")]
        )
        body = str(response)
        assert body.startswith("<p>hello</p>")
        assert "hx-swap-oob=\"outerHTML:[data-pjx-id='a']\"" in body


def test_absent_primary_yields_oob_fragments_only():
    with scope():
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        add_dirtied(["todos"])
        response = ReactiveResponse(primary=None, mounted=[entry("a", load="todo-1")])
        body = str(response)
        assert body.startswith("<div")
        assert "hx-swap-oob=\"outerHTML:[data-pjx-id='a']\"" in body


def test_region_already_in_the_primary_is_not_swapped_again():
    with scope():
        registry.register_instance(ResponseWidget.__name__, "a", "resolved-entry")
        add_dirtied(["todos"])
        primary = Markup('<div data-pjx-id="a">fresh</div>')
        response = ReactiveResponse(
            primary=primary, mounted=[entry("a", load="todo-1")]
        )
        assert response.body == primary
        assert "hx-swap-oob" not in str(response)


def test_malformed_mounted_header_degrades_to_primary_only():
    with scope():
        add_dirtied(["todos"])
        response = ReactiveResponse(primary=Markup("<p>hello</p>"), mounted="{not json")
        assert response.body == Markup("<p>hello</p>")

"""A header-only template answers its tag in markup, with no Python behind it.

Render-level: a parent template uses ``<Note …/>`` and nothing ever calls
``component("Note")``. The factory-level rules live in
test_classless_factory.py; this file only checks what the renderer does with
them.
"""

import threading
from pathlib import Path

import pytest

from pyjinhx.components import discovery
from pyjinhx.components.classless import component
from pyjinhx.rendering.pipeline import render


@pytest.fixture(autouse=True)
def reset_registry():
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None
    yield
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None


def write_tree(root: Path, note: str) -> type:
    """A page using ``<Note title="hi"/>`` and a ``note.pjx``; the page's class."""
    (root / "page.pjx").write_text('<main><Note title="hi"/></main>')
    (root / "note.pjx").write_text(note)
    discovery.build_registry(root, [])
    return component("Page")


def test_a_headed_template_renders_for_its_tag(tmp_path):
    page = write_tree(tmp_path, '{#def title: str #}<p class="note">{{ title }}</p>')

    html = render(page())

    assert '<p class="note">hi</p>' in html
    assert "<Note" not in html
    assert discovery.get_class("note") is component("Note")


def test_an_empty_header_is_enough(tmp_path):
    page = write_tree(tmp_path, "{#def #}<p>static</p>")

    assert "<p>static</p>" in render(page())


def test_a_headerless_template_leaves_the_tag_as_markup_and_is_read_once(
    tmp_path, monkeypatch
):
    page = write_tree(tmp_path, "<p>not a component</p>")
    note = tmp_path / "note.pjx"
    reads: list[Path] = []
    real = Path.read_text

    def read_text(self, *args, **kwargs):
        reads.append(self)
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)

    first = render(page())
    second = render(page())

    assert '<Note title="hi"' in first
    assert first == second
    assert reads.count(note) == 1
    assert discovery.get_class("note") is None


def test_a_tag_with_no_template_passes_through(tmp_path):
    (tmp_path / "page.pjx").write_text("<main><WebThing/></main>")
    discovery.build_registry(tmp_path, [])

    assert "<WebThing" in render(component("Page")())


def test_a_malformed_header_fails_the_render_naming_the_file(tmp_path):
    page = write_tree(tmp_path, "{#def title: = #}<p></p>")

    with pytest.raises(ValueError, match="note.pjx"):
        render(page())


def test_a_registered_class_wins_over_the_orphan(tmp_path):
    page = write_tree(tmp_path, "{#def title: str #}<p>orphan</p>")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "note.pjx").write_text("{#def title: str #}<p>declared</p>")
    declared = component("Note", template_dir=elsewhere)

    html = render(page())

    assert "<p>declared</p>" in html
    assert discovery.get_class("note") is declared


def test_concurrent_renders_of_a_never_built_tag_share_one_class(tmp_path):
    page = write_tree(tmp_path, "{#def title: str #}<p>{{ title }}</p>")
    outputs: list[str] = []
    barrier = threading.Barrier(2)

    def call():
        barrier.wait()
        outputs.append(render(page()))

    threads = [threading.Thread(target=call) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(outputs) == 2
    assert all("<p>hi</p>" in html for html in outputs)
    assert discovery.get_class("note") is component("Note")

"""L1.4.6 — the cross-cutting matrix for the whole classless surface.

Open subclass (#374), {#def#} parse (#375), class generation (#376), the stale
header warning (#377) and the component() factory (#378) each have their own
unit file. This one covers only what those files cannot see on their own: the
places two of those surfaces meet, and the render path none of them walks.
"""

import logging
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

from pyjinhx import discovery
from pyjinhx._component import BaseComponent, OpenComponent
from pyjinhx.classless import component
from pyjinhx.props_header import parse_props_header
from pyjinhx.rendering import render_level
from pyjinhx.segments import serialize
from pyjinhx.session import RenderSession


@pytest.fixture(autouse=True)
def reset_registry():
    """Each test starts from an empty published mapping."""
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None
    yield
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None


def write_template(directory: Path, tag: str, source: str) -> Path:
    """Write ``source`` to ``<directory>/<tag>.pjx`` and return the path."""
    path = directory / f"{tag}.pjx"
    path.write_text(source, encoding="utf-8")
    return path


def absolute_session() -> RenderSession:
    """A session that can load a descriptor's absolute template path.

    A classless class's descriptor names its template by absolute path, and
    Jinja's loader resolves such a name against a root of "/" — so the tests
    render the real generated class against its real file on disk instead of
    swapping in a descriptor that points somewhere loadable.
    """
    return RenderSession()


def _three_classes(tmp_path: Path) -> dict[str, type[OpenComponent]]:
    """One class per construction path, all three built in the same session.

    The point is that they are indistinguishable where ADR 0006 says they must
    be: header-built, placeholder and hand-written all open the same way.
    """
    write_template(tmp_path, "card", '{#def title: str = "hi" #}<div>{{ title }}</div>')
    write_template(tmp_path, "badge", "<div>plain</div>")

    class Panel(OpenComponent):
        title: str = "hi"

    return {
        "headed": component("Card", template_dir=tmp_path),
        "placeholder": component("Badge", template_dir=tmp_path),
        "handwritten": Panel,
    }


def test_every_construction_path_lands_on_the_open_base(tmp_path):
    """ADR 0006: a class that accepts extras subclasses OpenComponent, always."""
    for label, cls in _three_classes(tmp_path).items():
        assert issubclass(cls, OpenComponent), label
        assert cls.model_config.get("extra") == "allow", label


def test_every_construction_path_keeps_the_strict_core_underneath(tmp_path):
    """Open is an opt-in *subclass*, so the strict core is still the ancestor."""
    for label, cls in _three_classes(tmp_path).items():
        assert issubclass(cls, BaseComponent), label
        assert cls is not BaseComponent, label
        assert BaseComponent.model_config.get("extra") != "allow"


def test_every_construction_path_takes_an_undeclared_attribute(tmp_path):
    """Extras parity: the three paths agree on where an unknown key lands."""
    for label, cls in _three_classes(tmp_path).items():
        instance = cls(data_role="banner")  # pyright: ignore[reportCallIssue]
        assert instance.model_extra == {"data_role": "banner"}, label


MULTI_FIELD_TEMPLATE = (
    "{#def title: str, count: int = 0, active: bool = False, "
    "tags: list = [], meta: dict = {}, note: Optional[str] = None, "
    "weird: SomeUnknownType = None #}"
    "<div>{{ title }}:{{ count }}</div>"
)


def test_a_multi_field_header_survives_parse_build_and_placement(tmp_path):
    """Parse -> build -> register, on a header wide enough to be realistic."""
    write_template(tmp_path, "card", MULTI_FIELD_TEMPLATE)

    cls = component("Card", template_dir=tmp_path)
    fields = cls.model_fields

    assert issubclass(cls, OpenComponent)
    assert fields["title"].annotation is str
    assert fields["title"].is_required()
    assert fields["count"].annotation is int
    assert fields["count"].default == 0
    assert fields["active"].annotation is bool
    assert fields["active"].default is False
    assert fields["tags"].annotation is list
    assert fields["meta"].annotation is dict
    assert fields["note"].annotation == (str | None)
    assert discovery.get_class("card") is cls


def test_an_unrecognized_annotation_falls_back_to_any_end_to_end(tmp_path):
    """The header vocabulary is closed; anything outside it degrades to Any."""
    write_template(tmp_path, "card", MULTI_FIELD_TEMPLATE)

    cls = component("Card", template_dir=tmp_path)

    assert cls.model_fields["weird"].annotation is Any
    instance = cls(title="hi", weird=object())  # pyright: ignore[reportCallIssue]
    assert instance.weird is not None  # pyright: ignore[reportAttributeAccessIssue]


def test_the_descriptor_is_one_frozen_object_not_a_per_read_computation(tmp_path):
    """Invariant 5: descriptor facts are resolved once, at class placement."""
    path = write_template(
        tmp_path, "card", '{#def title: str = "hi" #}<div>{{ title }}</div>'
    )

    cls = component("Card", template_dir=tmp_path)
    first = cls.__pjx_descriptor__
    second = cls.__pjx_descriptor__

    assert first is second
    assert first.template_path == path
    assert first.strict is False
    assert first.has_stale_def_header is False


def test_rendering_never_recomputes_the_descriptor(tmp_path, monkeypatch):
    """N renders cost zero header parses: the probe ran at build time."""
    from pyjinhx import props_header

    write_template(tmp_path, "card", '{#def title: str = "hi" #}<div>{{ title }}</div>')
    cls = component("Card", template_dir=tmp_path)
    before = cls.__pjx_descriptor__

    calls: list[str] = []

    def spy(source: str):
        calls.append(source)
        return parse_props_header(source)

    monkeypatch.setattr(props_header, "parse_props_header", spy)

    session = absolute_session()
    for _ in range(3):
        render_level(cls(), session)

    assert calls == []
    assert cls.__pjx_descriptor__ is before


def stale_records(caplog) -> list[str]:
    """The stale-{#def#} warnings caplog saw, as messages."""
    return [r.getMessage() for r in caplog.records if "{#def#}" in r.getMessage()]


def test_a_nested_headed_template_is_not_reported_as_stale(tmp_path, caplog):
    """Subdirectory resolution must not lose the "built from this header" fact."""
    nested = tmp_path / "widgets"
    nested.mkdir()
    write_template(nested, "card", '{#def title: str = "hi" #}<div>{{ title }}</div>')

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        cls = component("Card", template_dir=tmp_path)
        render_level(cls(), absolute_session())

    assert issubclass(cls, OpenComponent)
    assert cls.__pjx_descriptor__.has_stale_def_header is False
    assert stale_records(caplog) == []


def test_a_malformed_header_warns_about_nothing_because_nothing_is_built(
    tmp_path, caplog
):
    """The parse error is the whole outcome; no class, so no stale report."""
    write_template(tmp_path, "card", "{#def title: str, *args #}<div></div>")

    with (
        caplog.at_level(logging.WARNING, logger="pyjinhx"),
        pytest.raises(ValueError),
    ):
        component("Card", template_dir=tmp_path)

    assert discovery.get_class("card") is None
    assert stale_records(caplog) == []


def test_a_class_built_under_concurrency_is_not_reported_as_stale(tmp_path, caplog):
    """The one class two racing callers agree on still owns its header."""
    write_template(tmp_path, "card", '{#def title: str = "hi" #}<div>{{ title }}</div>')

    results: list[type] = []
    barrier = threading.Barrier(2)

    def call():
        barrier.wait()
        results.append(component("Card", template_dir=tmp_path))

    threads = [threading.Thread(target=call) for _ in range(2)]
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        render_level(results[0](), absolute_session())

    assert results[0] is results[1]
    assert results[0].__pjx_descriptor__.has_stale_def_header is False
    assert stale_records(caplog) == []


def test_the_two_paths_do_not_borrow_each_others_header_state(tmp_path, caplog):
    """One classless class and one hand-written stale class, same session.

    The classless class stays silent and the hand-written one warns: the
    "built from this header" fact is per class, so neither can flip the other.
    """

    class StaleCard(BaseComponent):
        """Its co-located template (stale_card.pjx) still carries a header."""

        title: str = "default"

    # Named "Widget", not "Card": the warning message embeds the class name
    # verbatim, and "Card" is a substring of "StaleCard" — a same-named (or
    # substring-named) generated class would make the "did not leak into the
    # other's message" assertion below pass by accident even if it actually did.
    write_template(
        tmp_path, "widget", '{#def title: str = "hi" #}<div>{{ title }}</div>'
    )
    generated = component("Widget", template_dir=tmp_path)

    assert generated.__pjx_descriptor__.has_stale_def_header is False
    assert StaleCard.__pjx_descriptor__.has_stale_def_header is True

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        render_level(generated(), absolute_session())
        render_level(StaleCard(), RenderSession())

    messages = stale_records(caplog)
    assert len(messages) == 1, messages
    assert "StaleCard" in messages[0]
    assert generated.__name__ not in messages[0]


def test_concurrent_calls_for_two_different_headers_stay_unmixed(tmp_path, caplog):
    """Two tags, two headers, one lock: each class must get its own fields."""
    write_template(tmp_path, "card", '{#def title: str = "hi" #}<div>{{ title }}</div>')
    write_template(tmp_path, "badge", "{#def count: int = 7 #}<span>{{ count }}</span>")

    results: dict[str, type] = {}
    barrier = threading.Barrier(2)

    def call(name: str):
        barrier.wait()
        results[name] = component(name, template_dir=tmp_path)

    modules_before = set(sys.modules)
    threads = [threading.Thread(target=call, args=(n,)) for n in ("Card", "Badge")]
    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert set(results["Card"].model_fields) >= {"title"}
    assert "count" not in results["Card"].model_fields
    assert set(results["Badge"].model_fields) >= {"count"}
    assert "title" not in results["Badge"].model_fields
    assert discovery.get_class("card") is results["Card"]
    assert discovery.get_class("badge") is results["Badge"]
    assert stale_records(caplog) == []
    synthetic = {
        m
        for m in set(sys.modules) - modules_before
        if m.startswith("pyjinhx._classless_")
    }
    assert len(synthetic) <= 1


def test_a_header_built_class_renders_its_declared_fields_end_to_end(tmp_path):
    """Parse -> class -> descriptor -> render, with nothing swapped in between."""
    write_template(
        tmp_path,
        "card",
        "{#def title: str, count: int = 0 #}"
        '<article class="card">{{ title }} ({{ count }})</article>',
    )

    cls = component("Card", template_dir=tmp_path)
    instance = cls(title="Hello", count=3)  # pyright: ignore[reportCallIssue]
    output = serialize(render_level(instance, absolute_session()))

    assert issubclass(cls, OpenComponent)
    assert output == '<article class="card">Hello (3)</article>'


def test_an_extra_attribute_reaches_the_template_through_the_render_path(tmp_path):
    """Extras are part of the dumped context, so an open class can read one."""
    write_template(
        tmp_path,
        "card",
        "{#def title: str #}<article>{{ title }}/{{ subtitle }}</article>",
    )

    cls = component("Card", template_dir=tmp_path)
    instance = cls(title="Hello", subtitle="World")  # pyright: ignore[reportCallIssue]
    output = serialize(render_level(instance, absolute_session()))

    assert instance.model_extra == {"subtitle": "World"}
    assert output == "<article>Hello/World</article>"


def test_a_placeholder_class_renders_the_same_way(tmp_path):
    """No header means no declared props, and the render path does not care."""
    write_template(tmp_path, "badge", "<span>{{ text }}</span>")

    cls = component("Badge", template_dir=tmp_path)
    instance = cls(text="OK")  # pyright: ignore[reportCallIssue]
    output = serialize(render_level(instance, absolute_session()))

    assert issubclass(cls, OpenComponent)
    assert set(cls.model_fields) == {"id"}
    assert instance.model_extra == {"text": "OK"}
    assert output == "<span>OK</span>"

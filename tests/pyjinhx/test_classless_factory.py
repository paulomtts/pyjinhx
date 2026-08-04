"""Unit tests for component(), the lazy classless factory.

This file covers the factory itself only: name validation, the registry
hit that makes it idempotent, template lookup, header dispatch and the
descriptor the returned class carries. The cross-cutting matrix for the whole
classless surface is a separate file.
"""

import sys
import threading
from pathlib import Path

import pytest

from pyjinhx import discovery
from pyjinhx._component import BaseComponent, _OpenComponent
from pyjinhx.classless import component


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


@pytest.mark.parametrize("name", ["foo", "fooBar", "FOO", "Foo_Bar", "", "9Foo"])
def test_a_name_that_is_not_a_pascal_case_tag_is_rejected(name, tmp_path):
    with pytest.raises(ValueError):
        component(name, template_dir=tmp_path)


def test_a_bad_name_is_rejected_before_the_template_dir_is_touched():
    """Validation comes first, so a bad name never reports a filesystem problem."""
    with pytest.raises(ValueError):
        component("foo", template_dir="/nonexistent/directory")


def test_a_registered_tag_is_returned_unchanged(tmp_path):
    """A hand-declared component keeps its tag; the factory hands it back."""

    class Card(BaseComponent):
        pass

    discovery.register_class("card", Card)
    write_template(tmp_path, "card", "{#def title: str #}<div></div>")

    assert component("Card", template_dir=tmp_path) is Card
    assert discovery.get_class("card") is Card


def test_no_template_on_disk_raises(tmp_path):
    with pytest.raises(LookupError):
        component("Card", template_dir=tmp_path)


def test_no_template_on_disk_leaves_the_registry_untouched(tmp_path):
    with pytest.raises(LookupError):
        component("Card", template_dir=tmp_path)

    assert discovery.get_class("card") is None


def test_the_template_dir_defaults_to_the_one_discovery_walked(tmp_path):
    write_template(tmp_path, "card", "<div></div>")
    discovery.build_registry(tmp_path, [])

    cls = component("Card")

    assert cls.__name__ == "Card"


def test_no_template_dir_at_all_raises(tmp_path):
    """Nothing has told the process where templates live yet."""
    with pytest.raises(LookupError):
        component("Card")


def test_a_nested_template_is_found(tmp_path):
    """The walk is recursive, so a component in a subdirectory resolves."""
    nested = tmp_path / "widgets"
    nested.mkdir()
    write_template(nested, "card", "<div></div>")

    cls = component("Card", template_dir=tmp_path)

    assert cls.__name__ == "Card"


def test_a_headed_template_becomes_a_class_with_the_headers_props(tmp_path):
    write_template(
        tmp_path, "card", "{#def title: str, count: int = 3 #}<div>{{ title }}</div>"
    )

    cls = component("Card", template_dir=tmp_path)

    assert issubclass(cls, _OpenComponent)
    assert issubclass(cls, BaseComponent)
    assert cls.__name__ == "Card"
    assert cls.model_fields["title"].annotation is str
    assert cls.model_fields["title"].is_required()
    assert cls.model_fields["count"].default == 3


def test_a_headed_class_is_marked_classless(tmp_path):
    write_template(tmp_path, "card", "{#def title: str #}<div></div>")

    cls = component("Card", template_dir=tmp_path)

    assert cls._pjx_classless is True  # pyright: ignore[reportAttributeAccessIssue]


def test_a_headed_class_accepts_undeclared_attributes(tmp_path):
    """ADR 0006: a header declares what the template reads, not what may pass through."""
    write_template(tmp_path, "card", "{#def title: str #}<div></div>")

    cls = component("Card", template_dir=tmp_path)
    instance = cls(title="hi", data_role="banner")  # pyright: ignore[reportCallIssue]

    assert instance.model_extra == {"data_role": "banner"}


def test_a_malformed_header_propagates_the_parse_error(tmp_path):
    write_template(tmp_path, "card", "{#def title: str, *args #}<div></div>")

    with pytest.raises(ValueError, match="simple named props"):
        component("Card", template_dir=tmp_path)


def test_a_malformed_header_registers_nothing(tmp_path):
    write_template(tmp_path, "card", "{#def title: str, *args #}<div></div>")

    with pytest.raises(ValueError):
        component("Card", template_dir=tmp_path)

    assert discovery.get_class("card") is None


def test_a_header_less_template_becomes_a_permissive_placeholder(tmp_path):
    write_template(tmp_path, "card", "<div>{{ title }}</div>")

    cls = component("Card", template_dir=tmp_path)

    assert issubclass(cls, _OpenComponent)
    assert cls.__name__ == "Card"
    assert cls._pjx_classless is True  # pyright: ignore[reportAttributeAccessIssue]
    assert cls._pjx_template == "card"  # pyright: ignore[reportAttributeAccessIssue]


def test_a_placeholder_declares_no_props_and_takes_anything(tmp_path):
    """With no header there is nothing to declare, so every attribute is extra."""
    write_template(tmp_path, "card", "<div></div>")

    cls = component("Card", template_dir=tmp_path)
    instance = cls(title="hi", count="3")  # pyright: ignore[reportCallIssue]

    assert set(cls.model_fields) == {"id"}
    assert instance.model_extra == {"title": "hi", "count": "3"}


def test_the_returned_class_carries_a_descriptor_for_its_real_template(tmp_path):
    """Invariant 5: per-class facts are resolved once, never deferred to render."""
    path = write_template(tmp_path, "card", "{#def title: str #}<div></div>")

    cls = component("Card", template_dir=tmp_path)

    assert cls.__pjx_descriptor__.template_path == path


def test_a_placeholder_also_carries_a_descriptor_for_its_real_template(tmp_path):
    path = write_template(tmp_path, "card", "<div></div>")

    cls = component("Card", template_dir=tmp_path)

    assert cls.__pjx_descriptor__.template_path == path


def test_the_returned_class_is_relocated_off_the_generator_module(tmp_path):
    """build_component_class pins __module__ to props_header; placement is ours."""
    write_template(tmp_path, "card", "{#def title: str #}<div></div>")

    cls = component("Card", template_dir=tmp_path)

    assert cls.__module__ != "pyjinhx.props_header"
    module_file = sys.modules[cls.__module__].__file__
    assert module_file is not None
    assert Path(module_file).parent == tmp_path


def test_a_nested_template_relocates_to_its_own_directory(tmp_path):
    nested = tmp_path / "widgets"
    nested.mkdir()
    path = write_template(nested, "card", "<div></div>")

    cls = component("Card", template_dir=tmp_path)

    assert cls.__pjx_descriptor__.template_path == path


def test_the_new_class_is_published_under_its_tag(tmp_path):
    write_template(tmp_path, "card", "<div></div>")

    cls = component("Card", template_dir=tmp_path)

    assert discovery.get_class("card") is cls


def test_calling_twice_returns_the_same_class(tmp_path):
    write_template(tmp_path, "card", "{#def title: str #}<div></div>")

    first = component("Card", template_dir=tmp_path)
    second = component("Card", template_dir=tmp_path)

    assert first is second
    assert first.__pjx_descriptor__ is second.__pjx_descriptor__


def test_concurrent_calls_for_the_same_undeclared_tag_register_one_class(tmp_path):
    """Two threads racing on the same tag must not both win the registry.

    The loser's build must not leak a synthetic module into sys.modules: the
    check-then-register in component() has to be atomic with respect to other
    callers of the same tag.
    """
    write_template(tmp_path, "card", "<div></div>")

    results: list[type] = []
    barrier = threading.Barrier(2)

    def call():
        barrier.wait()
        results.append(component("Card", template_dir=tmp_path))

    threads = [threading.Thread(target=call) for _ in range(2)]
    modules_before = set(sys.modules)
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results[0] is results[1]
    assert discovery.get_class("card") is results[0]
    new_modules = set(sys.modules) - modules_before
    synthetic = {m for m in new_modules if m.startswith("pyjinhx._classless_")}
    assert len(synthetic) == 1


def test_a_classless_class_is_not_reported_as_carrying_a_stale_header(tmp_path):
    """It was built from that header, so the header is not leftover."""
    write_template(tmp_path, "card", "{#def title: str #}<div></div>")

    cls = component("Card", template_dir=tmp_path)

    assert cls.__pjx_descriptor__.has_stale_def_header is False

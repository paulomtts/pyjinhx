"""Unit tests for component(), the lazy classless factory.

This file covers the factory itself only: name validation, the registry
hit that makes it idempotent, template lookup, header dispatch and the
descriptor the returned class carries. The cross-cutting matrix for the whole
classless surface is a separate file.
"""

import re
import sys
import threading
from pathlib import Path

import pytest

from pyjinhx import discovery
from pyjinhx._component import BaseComponent, _OpenComponent
from pyjinhx.classless import component, component_for_tag


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


def test_a_dotted_name_that_does_not_import_names_the_template_file(tmp_path):
    path = write_template(tmp_path, "card", "{#def tone: no_such_pkg.Tone #}<b></b>")

    with pytest.raises(ValueError, match=re.escape(str(path))):
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


def test_a_header_import_that_calls_component_does_not_deadlock(tmp_path, monkeypatch):
    """Resolving a dotted name imports a module, which may build components too."""
    (tmp_path / "parts").mkdir()
    write_template(tmp_path / "parts", "badge", "<b></b>")
    (tmp_path / "reentrant_probe.py").write_text(
        "from pyjinhx.classless import component\n"
        f"Badge = component('Badge', template_dir={str(tmp_path / 'parts')!r})\n"
        "SIZE = 3\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "reentrant_probe", raising=False)
    write_template(tmp_path, "card", "{#def size: int = reentrant_probe.SIZE #}")

    results: list[type] = []
    thread = threading.Thread(
        target=lambda: results.append(component("Card", template_dir=tmp_path)),
        daemon=True,
    )
    thread.start()
    thread.join(timeout=5)

    assert not thread.is_alive(), "component() deadlocked on its own lock"
    assert results[0].model_fields["size"].default == 3
    assert discovery.get_class("badge") is not None


def test_a_classless_class_is_not_reported_as_carrying_a_stale_header(tmp_path):
    """It was built from that header, so the header is not leftover."""
    write_template(tmp_path, "card", "{#def title: str #}<div></div>")

    cls = component("Card", template_dir=tmp_path)

    assert cls.__pjx_descriptor__.has_stale_def_header is False


def count_reads(monkeypatch) -> list[Path]:
    """Record every ``Path.read_text`` call, still letting it read."""
    reads: list[Path] = []
    real = Path.read_text

    def read_text(self, *args, **kwargs):
        reads.append(self)
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    return reads


def test_a_headed_orphan_answers_its_tag(tmp_path):
    write_template(tmp_path, "note", "{#def title: str #}<p>{{ title }}</p>")
    discovery.build_registry(tmp_path, [])

    cls = component_for_tag("Note")

    assert cls is not None
    assert cls.__name__ == "Note"
    assert set(cls.model_fields) >= {"title"}
    assert discovery.get_class("note") is cls


def test_an_empty_header_still_opts_in(tmp_path):
    write_template(tmp_path, "note", "{#def #}<p>static</p>")
    discovery.build_registry(tmp_path, [])

    assert component_for_tag("Note") is discovery.get_class("note") is not None


def test_a_headerless_orphan_is_not_a_component_and_is_read_once(tmp_path, monkeypatch):
    write_template(tmp_path, "note", "<p>just a template</p>")
    discovery.build_registry(tmp_path, [])
    reads = count_reads(monkeypatch)

    assert component_for_tag("Note") is None
    assert component_for_tag("Note") is None
    assert reads == [tmp_path / "note.pjx"]
    assert discovery.get_class("note") is None


def test_a_tag_with_no_template_touches_no_file(tmp_path, monkeypatch):
    write_template(tmp_path, "note", "{#def title: str #}<p></p>")
    discovery.build_registry(tmp_path, [])

    def refuse(*args, **kwargs):
        raise AssertionError("a tag with no template reached the filesystem")

    for name in ("read_text", "open", "stat", "is_file", "exists", "rglob"):
        monkeypatch.setattr(Path, name, refuse)

    assert component_for_tag("WebThing") is None


def test_a_malformed_orphan_header_names_its_file(tmp_path):
    path = write_template(tmp_path, "note", "{#def title: = #}<p></p>")
    discovery.build_registry(tmp_path, [])

    with pytest.raises(ValueError, match=str(path)):
        component_for_tag("Note")
    assert discovery.get_class("note") is None


def test_a_registered_class_wins_over_the_orphan(tmp_path, monkeypatch):
    write_template(tmp_path, "note", "{#def title: str #}<p></p>")
    discovery.build_registry(tmp_path, [])

    class Note(BaseComponent):
        pass

    discovery.register_class("note", Note)
    reads = count_reads(monkeypatch)

    assert component_for_tag("Note") is Note
    assert reads == []


def test_component_returns_the_class_the_tag_built(tmp_path):
    write_template(tmp_path, "note", "{#def title: str #}<p></p>")
    discovery.build_registry(tmp_path, [])

    built = component_for_tag("Note")

    assert component("Note") is built


def test_the_tag_returns_the_class_component_built(tmp_path):
    write_template(tmp_path, "note", "{#def title: str #}<p></p>")
    discovery.build_registry(tmp_path, [])

    built = component("Note")

    assert component_for_tag("Note") is built


def test_component_still_builds_a_headerless_orphan_the_tag_declined(tmp_path):
    write_template(tmp_path, "note", "<p></p>")
    discovery.build_registry(tmp_path, [])
    assert component_for_tag("Note") is None

    cls = component("Note")

    assert issubclass(cls, _OpenComponent)
    assert component_for_tag("Note") is cls


def test_two_headed_orphans_with_one_stem_are_refused_naming_both(tmp_path):
    for directory in ("a", "b"):
        (tmp_path / directory).mkdir()
        write_template(tmp_path / directory, "note", "{#def title: str #}<p></p>")
    discovery.build_registry(tmp_path, [])

    with pytest.raises(LookupError) as raised:
        component_for_tag("Note")

    assert str(tmp_path / "a" / "note.pjx") in str(raised.value)
    assert str(tmp_path / "b" / "note.pjx") in str(raised.value)
    assert discovery.get_class("note") is None


def test_one_headed_orphan_beside_a_headerless_namesake_is_still_ambiguous(
    tmp_path,
):
    """Picking the headed one would make the answer depend on file contents."""
    for directory, source in (("a", "<p></p>"), ("b", "{#def #}<p></p>")):
        (tmp_path / directory).mkdir()
        write_template(tmp_path / directory, "note", source)
    discovery.build_registry(tmp_path, [])

    with pytest.raises(LookupError, match="note.pjx"):
        component_for_tag("Note")


def test_headerless_orphans_sharing_a_stem_stay_plain_templates(tmp_path):
    for directory in ("a", "b"):
        (tmp_path / directory).mkdir()
        write_template(tmp_path / directory, "note", "<p></p>")
    discovery.build_registry(tmp_path, [])

    assert component_for_tag("Note") is None


def test_an_explicit_component_call_settles_an_ambiguous_stem(tmp_path):
    for directory in ("a", "b"):
        (tmp_path / directory).mkdir()
        write_template(tmp_path / directory, "note", "{#def title: str #}<p></p>")
    discovery.build_registry(tmp_path, [])

    chosen = component("Note")

    assert component_for_tag("Note") is chosen


def test_concurrent_tag_misses_for_one_orphan_build_one_class(tmp_path):
    write_template(tmp_path, "note", "{#def title: str #}<p></p>")
    discovery.build_registry(tmp_path, [])

    results: list[type | None] = []
    barrier = threading.Barrier(2)

    def call():
        barrier.wait()
        results.append(component_for_tag("Note"))

    threads = [threading.Thread(target=call) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results[0] is not None
    assert results[0] is results[1]
    assert discovery.get_class("note") is results[0]


def test_a_header_declaring_id_builds_a_class_that_requires_it(tmp_path):
    write_template(tmp_path, "card", "{#def id: str #}<div id={{ id }}></div>")

    cls = component("Card", template_dir=tmp_path)

    assert cls.auto_id is False
    assert cls(id="x").id == "x"  # pyright: ignore[reportCallIssue]
    with pytest.raises(ValueError, match="id is required"):
        cls()


def test_a_headed_orphan_resolves_its_dotted_names(tmp_path):
    write_template(
        tmp_path, "note", "{#def size: int = tests.pyjinhx.header_names.PAGE_SIZE #}"
    )
    discovery.build_registry(tmp_path, [])

    cls = component_for_tag("Note")

    assert cls is not None
    assert cls.model_fields["size"].default == 25


def test_an_orphan_naming_a_missing_import_names_its_file(tmp_path):
    path = write_template(tmp_path, "note", "{#def tone: no_such_pkg.Tone #}")
    discovery.build_registry(tmp_path, [])

    with pytest.raises(ValueError, match=re.escape(str(path))):
        component_for_tag("Note")

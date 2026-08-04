import ast
import dataclasses
import inspect
from collections.abc import Mapping
from pathlib import Path

import pytest

import pyjinhx.descriptor
from pyjinhx.descriptor import ClassDescriptor


class Base:
    """Stand-in ancestor class for provenance values — provenance holds classes."""


class Child(Base):
    pass


def make_descriptor(
    template_path: Path = Path("cards/card.pjx"),
    slot_fields: frozenset[str] = frozenset({"header", "body"}),
    children_field: str | None = None,
    css_paths: tuple[Path, ...] = (Path("cards/card.css"),),
    js_paths: tuple[Path, ...] = (Path("cards/card.js"),),
    strict: bool = True,
    provenance: "Mapping[str, type] | None" = None,
) -> ClassDescriptor:
    if provenance is None:
        provenance = {"template": Child, "css": Base, "js": Base}
    return ClassDescriptor(
        template_path=template_path,
        slot_fields=slot_fields,
        children_field=children_field,
        css_paths=css_paths,
        js_paths=js_paths,
        strict=strict,
        provenance=provenance,
    )


class TestClassDescriptorShape:
    def test_constructs_with_all_six_fields_and_reads_them_back(self):
        descriptor = ClassDescriptor(
            template_path=Path("cards/card.pjx"),
            slot_fields=frozenset({"header", "body"}),
            children_field=None,
            css_paths=(Path("cards/card.css"),),
            js_paths=(Path("cards/card.js"),),
            strict=True,
            provenance={"template": Child, "css": Base, "js": Base},
        )
        assert descriptor.template_path == Path("cards/card.pjx")
        assert descriptor.slot_fields == frozenset({"header", "body"})
        assert descriptor.css_paths == (Path("cards/card.css"),)
        assert descriptor.js_paths == (Path("cards/card.js"),)
        assert descriptor.strict is True
        assert descriptor.provenance == {"template": Child, "css": Base, "js": Base}

    def test_exposes_exactly_the_eight_declared_fields(self):
        names = [field.name for field in dataclasses.fields(ClassDescriptor)]
        assert names == [
            "template_path",
            "slot_fields",
            "children_field",
            "css_paths",
            "js_paths",
            "strict",
            "provenance",
            "has_stale_def_header",
        ]

    def test_no_field_has_a_default_except_the_stale_header_flag(self):
        # Construction is always a resolver's job (#272-#276); a bare
        # ClassDescriptor() must never be a legal call. has_stale_def_header is
        # the sole deliberate exception: it is a defaulted, keyword-friendly
        # field appended last so every existing call site keeps constructing
        # without edits.
        for field in dataclasses.fields(ClassDescriptor):
            if field.name == "has_stale_def_header":
                assert field.default is False
                continue
            assert field.default is dataclasses.MISSING
            assert field.default_factory is dataclasses.MISSING
        with pytest.raises(TypeError):
            ClassDescriptor()  # type: ignore[call-arg]

    def test_is_slotted_so_instances_have_no_dict(self):
        assert not hasattr(make_descriptor(), "__dict__")


class TestClassDescriptorIsFrozen:
    @pytest.mark.parametrize(
        ("field_name", "value"),
        [
            ("template_path", Path("other.pjx")),
            ("slot_fields", frozenset()),
            ("children_field", "other"),
            ("css_paths", ()),
            ("js_paths", ()),
            ("strict", False),
            ("provenance", {}),
        ],
    )
    def test_assigning_any_field_raises(self, field_name: str, value: object):
        descriptor = make_descriptor()
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(descriptor, field_name, value)


class TestClassDescriptorEquality:
    def test_equal_field_values_compare_equal(self):
        # rebuild_class_descriptor replaces the whole object; equality is how a
        # test asserts a no-op rebuild produced an equivalent descriptor. The
        # rebuild itself is exercised in test_component_descriptor.py, which may
        # import _component.py — this module may not.
        assert make_descriptor() == make_descriptor()

    def test_differing_field_values_compare_unequal(self):
        assert make_descriptor() != make_descriptor(strict=False)

    def test_is_not_hashable_because_provenance_is_a_plain_mapping(self):
        # Documented, accepted consequence: a dict-valued field makes the
        # generated __hash__ raise. Nothing downstream keys a cache by
        # descriptor, so this is not worked around (see module comment).
        with pytest.raises(TypeError):
            hash(make_descriptor())


class TestClassDescriptorEmptyCollections:
    def test_no_slots_no_assets_no_provenance_is_valid(self):
        descriptor = ClassDescriptor(
            template_path=Path("plain.pjx"),
            slot_fields=frozenset(),
            children_field=None,
            css_paths=(),
            js_paths=(),
            strict=False,
            provenance={},
        )
        assert descriptor.slot_fields == frozenset()
        assert descriptor.css_paths == ()
        assert descriptor.js_paths == ()
        assert descriptor.provenance == {}


class TestClassDescriptorPerKindIndependence:
    def test_provenance_kinds_can_name_different_ancestors(self):
        # ADR 0010: template/css/js resolve independently. If a future edit
        # collapsed them into one value, this stops being expressible.
        descriptor = make_descriptor(provenance={"template": Child, "css": Base})
        assert descriptor.provenance["template"] is Child
        assert descriptor.provenance["template"] is not descriptor.provenance.get("css")

    def test_css_and_js_paths_are_separate_fields(self):
        descriptor = make_descriptor(
            css_paths=(Path("a.css"),), js_paths=(Path("b.js"), Path("c.js"))
        )
        assert descriptor.css_paths == (Path("a.css"),)
        assert descriptor.js_paths == (Path("b.js"), Path("c.js"))


def test_descriptor_module_is_import_pure():
    tree = ast.parse(inspect.getsource(pyjinhx.descriptor))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "descriptor.py must not use relative imports"
            names = [node.module or ""]
        else:
            continue
        internal = [n for n in names if n.startswith("pyjinhx")]
        assert not internal, (
            f"descriptor.py must not import internal modules: {internal}"
        )

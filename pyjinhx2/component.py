"""The component base class: a strict Pydantic model with mandatory field declaration.

All components reject undeclared kwargs at construction time. This keeps the core
lightweight and lets the renderer avoid walking arbitrary instance attributes.

Imports pydantic and ClassDescriptor from descriptor.py (sole sanctioned import
from a higher-level module). The import graph is enforced statically by
tests/pyjinhx2/test_import_graph.py.
"""

import itertools
import json
import re
import sys
import types
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any, ClassVar, Union, get_args, get_origin

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from pyjinhx2.descriptor import ClassDescriptor

_auto_id_counter = itertools.count(1)


def _auto_id() -> str:
    """Generate a process-unique component id (``pjx-<n>``)."""
    return f"pjx-{next(_auto_id_counter)}"


_ATTR_NAME_RE = re.compile(r"[A-Za-z@:][A-Za-z0-9_.:@-]*")


def validate_attr_value(value: str) -> str:
    """Reject values that could break out of a double-quoted HTML attribute.

    Belt-and-suspenders construction-time guard complementing autoescape:
    autoescape handles text content, but attribute quoting is structural and
    must be caught before the value reaches the template.
    Post-construction mutation bypasses this check.
    """
    if '"' in value:
        raise ValueError("attribute values must not contain '\"'")
    return value


def validate_extra_attrs(value: dict[str, str]) -> dict[str, str]:
    """Reject attribute names/values that could break out of an HTML attribute.

    Values with one quote type are fine: emission picks the other quote.
    Values with both are inexpressible.
    """
    for name, attr_value in value.items():
        if not _ATTR_NAME_RE.fullmatch(name):
            raise ValueError(f"extra_attrs name {name!r} is not a valid attribute name")
        if '"' in attr_value and "'" in attr_value:
            raise ValueError("attribute values must not contain both '\"' and \"'\"")
    return value


AttrValue = Annotated[str, AfterValidator(validate_attr_value)]
ExtraAttrs = Annotated[dict[str, str], AfterValidator(validate_extra_attrs)]


class PjxSlot:
    """Marker (in a field's ``Annotated`` metadata) for a raw-HTML slot field —
    its string value is emitted unescaped (invariant 6, the autoescape exemption).
    Use via the ``Slot`` alias.

    ``children=True`` additionally flags the field as the target for a
    PascalCase tag's nested children (use via the ``Children`` alias).

    Purely descriptive at this layer: nothing here escapes, wraps or renders.
    The render-time half (Markup-wrapping strings, opaque component nodes) is
    L1 work and lives above component.py in the import graph.
    """

    def __init__(self, children: bool = False) -> None:
        self.children = children


def _is_slot_field(cls: type, field_name: str) -> bool:
    """True when ``field_name`` is a raw-HTML slot on ``cls``.

    A field qualifies either by being the model's designated children field, or
    by carrying a :class:`PjxSlot` marker in its ``Annotated`` metadata. Unknown
    field names are not slots.
    """
    if field_name == getattr(cls, "_pjx_children_field", None):
        return True
    fields = getattr(cls, "model_fields", {})
    field = fields.get(field_name)
    return field is not None and any(isinstance(m, PjxSlot) for m in field.metadata)


def _is_json_coercible_annotation(annotation: Any) -> bool:
    """A field is a JSON-coercion candidate if, once ``None`` is stripped from
    a ``T | None`` union, exactly one type remains and it's ``list``, ``dict``,
    or a ``BaseModel`` subclass. Unions that keep ``str`` (e.g. ``str | list``,
    and ``Slot``/``Children``) are left alone — a JSON-looking string there is
    ambiguous, and for a slot it is almost certainly literal markup."""
    if get_origin(annotation) in (Union, types.UnionType):
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) != 1:
            return False
        annotation = args[0]
    origin = get_origin(annotation) or annotation
    if origin in (list, dict):
        return True
    return isinstance(origin, type) and issubclass(origin, BaseModel)


_PASCAL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _pascal_to_snake(name: str) -> str:
    """Convert a PascalCase/CamelCase identifier to snake_case."""
    return _PASCAL_BOUNDARY_RE.sub("_", name).lower()


def _defining_module_dir(cls: type) -> Path:
    """Directory of the module that defined ``cls``."""
    module = sys.modules.get(cls.__module__)
    file = getattr(module, "__file__", None)
    if file is None:
        raise NotImplementedError(
            f"{cls.__name__} is defined in module {cls.__module__!r}, which has "
            f"no file on disk; template and asset resolution have no directory "
            f"to probe from."
        )
    return Path(file).parent


def _template_candidate(cls: type) -> Path:
    """Compute the expected template path for ``cls``: class_name.pjx in its module directory."""
    return _defining_module_dir(cls) / f"{_pascal_to_snake(cls.__name__)}.pjx"


def _asset_candidate(cls: type, kind: str) -> Path:
    """Compute the expected asset path for ``cls``: class_name.<kind> in its module directory."""
    return _defining_module_dir(cls) / f"{_pascal_to_snake(cls.__name__)}.{kind}"


def _resolution_ancestors(cls: type) -> list[type]:
    """``cls``'s MRO, nearest first, truncated before ``BaseComponent``.

    The classes willing to inherit a template (or, per-kind, an asset) from.
    ``BaseComponent`` itself is excluded: it never gets a descriptor — pydantic
    does not fire ``__pydantic_init_subclass__`` for the class that declares the
    hook — so it has no template to lend.
    """
    ancestors: list[type] = []
    for klass in cls.__mro__:
        if klass is BaseComponent:
            break
        ancestors.append(klass)
    return ancestors


def _walk_template(cls: type) -> tuple[Path, type | None]:
    """The template MRO walk, run once and reported in full.

    Returns ``(path, owner)``: the template ``cls`` renders with, and the
    ancestor a probe proved owns it — or ``None`` when the answer came from the
    last ancestor's candidate, which is returned *without* a probe (ADR 0007's
    budget). An unprobed candidate has no proven owner, so it names none.

    Single source of truth for the walk: `_resolve_template_path` and
    `_resolve_provenance` both read this one result, so adding provenance costs
    zero extra `is_file` calls.
    """
    ancestors = _resolution_ancestors(cls)
    for ancestor in ancestors[:-1]:
        candidate = _template_candidate(ancestor)
        if candidate.is_file():
            return candidate, ancestor
    return _template_candidate(ancestors[-1]), None


def _walk_asset(cls: type, kind: str) -> tuple[Path | None, type | None]:
    """The MRO walk for one asset kind, run once and reported in full.

    Returns ``(path, owner)``: the nearest ancestor's co-located ``.<kind>``
    file and the ancestor that owns it, or ``(None, None)`` when no ancestor
    has one.

    Every ancestor is probed, including the last. The template walk can return
    its final candidate unprobed because a component must render *something*,
    so a path is the answer either way; an asset is optional, so claiming an
    unprobed path would attach a stylesheet that is not there.
    """
    for ancestor in _resolution_ancestors(cls):
        candidate = _asset_candidate(ancestor, kind)
        if candidate.is_file():
            return candidate, ancestor
    return None, None


def _resolve_template_path(cls: type) -> Path:
    """The template ``cls`` renders with: the nearest ancestor's candidate that exists on disk.

    Walking supports subclasses: ``class DangerButton(PJXButton)`` becomes a
    three-line class instead of a copied template that drifts. The last ancestor's
    candidate is returned without a probe — it is the answer whether or not the
    file is there.
    """
    return _walk_template(cls)[0]


def _resolve_slot_fields(cls: type) -> frozenset[str]:
    """The declared fields of ``cls`` that are raw-HTML slots.

    A type-level fact, resolved once per class at registration: which fields
    are slots, not which one receives a tag's nested children (that precedence
    is L1's). Declared fields only — ``model_extra`` is never walked, so the
    strict core keeps its promise that undeclared keys stay untouched.
    """
    fields = getattr(cls, "model_fields", {})
    return frozenset(name for name in fields if _is_slot_field(cls, name))


def _resolve_asset_paths(cls: type) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """The co-located stylesheet and script ``cls`` ships with, each resolved by
    its own nearest-ancestor walk.

    Each kind yields a one-element tuple when a file was found and an empty one
    when it was not. The walks are independent: a subclass can keep its parent's
    stylesheet while defining its own script, or have neither.
    """
    css_path, _ = _walk_asset(cls, "css")
    js_path, _ = _walk_asset(cls, "js")
    return (
        () if css_path is None else (css_path,),
        () if js_path is None else (js_path,),
    )


def _resolve_strict(cls: type[BaseModel]) -> bool:
    """The ADR 0006 mode, recorded once per class so render.py branches per class instead of per render."""
    return cls.model_config.get("extra") == "forbid"


def _resolve_provenance(cls: type) -> Mapping[str, type]:
    """Which ancestor supplied each resolved kind — ADR 0010's free provenance,
    for error messages and the dependency graph.

    A kind appears only when a probe proved a file exists. The template key is
    omitted when the walk ended on the unprobed fallback, and the css/js keys
    when no ancestor had the file at all — in both cases no ancestor was proven
    to own anything, so naming one would be a guess.
    """
    owners: dict[str, type] = {}
    _, template_owner = _walk_template(cls)
    if template_owner is not None:
        owners["template"] = template_owner
    for kind in ("css", "js"):
        _, owner = _walk_asset(cls, kind)
        if owner is not None:
            owners[kind] = owner
    return owners


def _resolve_class_descriptor(cls: type[BaseModel]) -> ClassDescriptor:
    """Build the ClassDescriptor for ``cls`` by invoking all resolver helpers.

    Each kind's walk runs exactly once here and feeds both the path field and
    its provenance entry; calling the single-purpose resolvers side by side
    would probe the same ancestors twice.
    """
    template_path, template_owner = _walk_template(cls)
    css_path, css_owner = _walk_asset(cls, "css")
    js_path, js_owner = _walk_asset(cls, "js")
    provenance = {
        kind: owner
        for kind, owner in (
            ("template", template_owner),
            ("css", css_owner),
            ("js", js_owner),
        )
        if owner is not None
    }
    return ClassDescriptor(
        template_path=template_path,
        slot_fields=_resolve_slot_fields(cls),
        css_paths=() if css_path is None else (css_path,),
        js_paths=() if js_path is None else (js_path,),
        strict=_resolve_strict(cls),
        provenance=provenance,
    )


class BaseComponent(BaseModel):
    """Base for all components: strict field validation with auto-id support."""

    model_config = ConfigDict(extra="forbid")

    auto_id: ClassVar[bool] = True

    _pjx_descriptor: ClassVar[ClassDescriptor]

    id: str = Field(
        default_factory=_auto_id,
        description="The unique ID for this component. Auto-generated when omitted.",
    )

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Validate reserved fields and build the ClassDescriptor."""
        super().__pydantic_init_subclass__(**kwargs)
        if "auto_id" in cls.model_fields:
            raise TypeError(
                f"auto_id must remain a ClassVar[bool]; found instance field on "
                f"{cls.__name__}. Write `auto_id = False` or "
                f"`auto_id: ClassVar[bool] = False` — an unqualified annotation "
                f"turns it into a model field and silently disables the opt-out."
            )
        id_field = cls.model_fields.get("id")
        if id_field is None:
            raise TypeError(
                f"{cls.__name__} removes the reserved id field; id must stay a "
                f"str model field so auto-id and id validation keep working."
            )
        if id_field.annotation is not str:
            raise TypeError(
                f"{cls.__name__} redeclares the reserved id field as "
                f"{id_field.annotation}; id must remain typed str so "
                f"_validate_id and _require_explicit_id keep their meaning."
            )
        cls._pjx_descriptor = _resolve_class_descriptor(cls)

    @model_validator(mode="before")
    @classmethod
    def _require_explicit_id(cls, data: object) -> object:
        """Runs before field defaults, so it is the only hook that can see an
        omitted ``id`` and stop ``default_factory`` from silently filling it."""
        if cls.auto_id:
            return data
        if isinstance(data, dict) and data.get("id"):
            return data
        raise ValueError(f"{cls.__name__} sets auto_id = False, so id is required")

    @model_validator(mode="before")
    @classmethod
    def _coerce_json_string_attrs(cls, data: object) -> object:
        """A tag attribute always arrives as a string (Jinja renders the tag
        before it's parsed). For a field typed ``list``/``dict``/a ``BaseModel``,
        a JSON-looking string (``{...}``/``[...]``) is parsed before Pydantic
        sees it, so ``<Child sources="{{ sources | tojson }}"/>`` just works
        instead of every such component hand-rolling the same ``BeforeValidator``.

        Declared fields only: this never reads or writes ``model_extra``, so the
        strict core keeps its promise that undeclared keys are never walked."""
        if not isinstance(data, dict):
            return data
        for name, field in cls.model_fields.items():
            value = data.get(name)
            if not isinstance(value, str):
                continue
            text = value.strip()
            if not text or text[0] not in "{[":
                continue
            if not _is_json_coercible_annotation(field.annotation):
                continue
            try:
                data[name] = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{cls.__name__}.{name}: invalid JSON attribute value"
                ) from exc
        return data

    @field_validator("id", mode="before")
    @classmethod
    def _validate_id(cls, value: object) -> str:
        if not value:
            return _auto_id()
        return str(value)


Slot = Annotated[str | BaseComponent, PjxSlot()]
Children = Annotated[str | BaseComponent, PjxSlot(children=True)]

"""The component base class: a strict Pydantic model, and nothing more (ADR 0006).

v0.x's BaseComponent was ``extra="allow"``, so every render had to walk the
undeclared keys of every instance — the walk that caused the #240 crash. Here the
core is closed: an undeclared kwarg is a ValidationError at construction, and the
renderer never has to look. Extra-field ergonomics belong on a separate open
opt-in subclass (L1), not on this class.

Imports pydantic, plus the one sanctioned edge this issue (#271) adds: importing
``ClassDescriptor`` from descriptor.py to build and attach it in
``__pydantic_init_subclass__``. component.py still sits below descriptor.py and
render.py in the import graph and must never reach into render.py, session.py, or
reactive/ — the ClassDescriptor import is the sole declared exception, enforced
statically by tests/pyjinhx2/test_import_graph.py rather than left as a comment
nobody checks.
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

# Process-wide, never per-class: ids must be unique across every subclass, since
# they end up as HTML ids on the same page. ``count.__next__`` is atomic under
# the GIL, so concurrent construction needs no extra locking.
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


def _defining_module_dir(cls: type) -> Path:
    """Directory of the module that defined ``cls`` — the root every co-located
    probe starts from (ADR 0007).

    Raises for a class whose module has no file on disk (exec'd, REPL-defined,
    synthesised). There is genuinely no directory to probe from, so #271 fails
    at class-definition time rather than inventing one; #272 and #276 inherit
    this guard when they replace the stubs that call it.
    """
    module = sys.modules.get(cls.__module__)
    file = getattr(module, "__file__", None)
    if file is None:
        raise NotImplementedError(
            f"{cls.__name__} is defined in module {cls.__module__!r}, which has "
            f"no file on disk; template and asset resolution have no directory "
            f"to probe from."
        )
    return Path(file).parent


def _resolve_template_path(cls: type) -> Path:
    """STUB — #272 (single probe) and #273 (MRO walk) replace this in place.

    Returns the naive co-located path: it does not touch the filesystem and does
    not walk the MRO. The real ADR 0007 probe is #272's, the per-kind ancestor
    walk is #273's, and the missing-template message is #277's. Nothing at L0
    reads this value yet, so a not-yet-probed path cannot mislead anything.
    """
    return _defining_module_dir(cls) / f"{cls.__name__}.pjx"


def _resolve_slot_fields(cls: type) -> frozenset[str]:
    """STUB — #275 replaces this in place with real slot-field detection
    (``_is_slot_field`` over ``model_fields``). Empty until then."""
    return frozenset()


def _resolve_asset_paths(cls: type) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """STUB — #276 replaces this in place with co-located css/js discovery,
    resolved per-kind up the MRO (ADR 0010). Returns ``(css_paths, js_paths)``
    as one call because both kinds probe the same directory.

    Calls :func:`_defining_module_dir` for its side effect only: a class with no
    module file must fail here too, not silently report "no assets".
    """
    _defining_module_dir(cls)
    return ((), ())


def _resolve_strict(cls: type[BaseModel]) -> bool:
    """The ADR 0006 mode, recorded once per class so render.py branches per
    class instead of per render.

    Not a stub: this is real data available today. Reading the class's own
    pydantic config means L1's open opt-in subclass flips this to ``False`` with
    no further wiring.
    """
    return cls.model_config.get("extra") == "forbid"


def _resolve_provenance(cls: type) -> Mapping[str, type]:
    """STUB — #274 replaces this in place, mapping each kind (``"template"``,
    ``"css"``, ``"js"``) to the ancestor class that supplied it. Empty until
    then; the kinds are #274's to choose, not this stub's to predict."""
    return {}


def _resolve_class_descriptor(cls: type[BaseModel]) -> ClassDescriptor:
    """Build the one :class:`ClassDescriptor` for ``cls`` (invariant 5).

    The single seam behind which #272-#276 land. They replace the ``_resolve_*``
    helpers above **in place**; this function's name, signature and its one call
    site in ``BaseComponent.__pydantic_init_subclass__`` are the contract that
    does not move. Exceptions from any helper propagate unchanged, so a failure
    surfaces at the ``class Foo(BaseComponent): ...`` statement exactly like a
    pydantic model-build error does.

    Returns a whole object. Nothing partially constructs a descriptor or edits
    one after the fact — that is what ``frozen=True`` is there to enforce, and
    what lets #278's dev-reload rebuild simply reassign the class attribute.
    """
    css_paths, js_paths = _resolve_asset_paths(cls)
    return ClassDescriptor(
        template_path=_resolve_template_path(cls),
        slot_fields=_resolve_slot_fields(cls),
        css_paths=css_paths,
        js_paths=js_paths,
        strict=_resolve_strict(cls),
        provenance=_resolve_provenance(cls),
    )


class BaseComponent(BaseModel):
    """Base for all components: declared fields only, undeclared kwargs rejected.

    Deliberately minimal otherwise. Slot, attribute coercion and quote-safety are
    separate concerns and land as their own changes. The auto-id counter is the
    single chartered construction-time side effect (ADR 0004/0009); nothing else
    here runs one.
    """

    model_config = ConfigDict(extra="forbid")

    # Construction-time control, not model data: a ClassVar is invisible to
    # model_fields, so it never collides with extra="forbid" or serialization.
    # Opt out per component class with ``class Foo(BaseComponent): auto_id = False``.
    auto_id: ClassVar[bool] = True

    id: str = Field(
        default_factory=_auto_id,
        description="The unique ID for this component. Auto-generated when omitted.",
    )

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Reject subclasses that shadow a reserved name (invariant 5: once per
        class, at definition time — never per instance, never per render).

        Pydantic calls this after ``model_fields`` is built, so both checks are
        plain reads of already-computed class facts.
        """
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


# Defined after BaseComponent so the union member resolves at definition time.
# The full ``str | BaseComponent`` union is kept at L0 even though only the
# ``str`` half gets behavior here, so the type does not change under callers
# when L1 lands opaque component nodes (ADR 0003).
Slot = Annotated[str | BaseComponent, PjxSlot()]
Children = Annotated[str | BaseComponent, PjxSlot(children=True)]

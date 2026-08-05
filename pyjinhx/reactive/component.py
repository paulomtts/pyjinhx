"""ReactiveComponent: a component whose ``load()`` is memoized per request.

The wrap is installed once, when the subclass is defined, and rebound onto the
class exactly like the ClassDescriptor is - per-class derived facts are computed
at registration, never per render.
"""

import hashlib
import inspect
import json
from collections.abc import Callable, Iterable
from enum import Enum
from typing import (
    Annotated,
    Any,
    ClassVar,
    Literal,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from pydantic import TypeAdapter, ValidationError
from pydantic.fields import FieldInfo

from pyjinhx._component import BaseComponent
from pyjinhx.app_context import resolve_load_context_param
from pyjinhx.reactive.backend import CachePolicy
from pyjinhx.reactive.cache import cache_get, cache_has, cache_put
from pyjinhx.reactive.keys import coerce_load_key_str, coerce_reactive_key
from pyjinhx.session import get_load_context


class ReactiveComponent(BaseComponent):
    """Base for components that fetch their data in ``load()``.

    Every subclass's ``load()`` is routed through the request-scoped load cache:
    the first call in a request runs the real body, later calls in that same
    request reuse its result. Declaring ``react=(...)`` on the subclass reverse-
    indexes the cached result under those keys, so dirtying one evicts it.
    """

    _pjx_react_keys: tuple[str, ...] = ()
    """Normalized reactive keys this class's cached load result depends on."""

    _pjx_key_field: ClassVar[str | None] = None
    """Name of this class's PjxKey-marked field, or None when it has none."""

    _pjx_key_adapter: ClassVar[Any] = None
    """Validator for the PjxKey field's declared type, or None when it has none.
    Restores a load key that round-tripped through a string medium (the
    ``data-pjx-load`` attribute) to the type ``load()`` declares."""

    state_hash_exclude: ClassVar[frozenset[str]] = frozenset({"id"})
    """Field names left out of the state hash. A subclass's value replaces this
    one outright rather than adding to it."""

    _pjx_cache_policy: ClassVar[CachePolicy | Literal[False] | None] = None
    """This class's cross-request cache policy: a CachePolicy that overrides the
    process default, False for tier-1-only, or None when the class said nothing
    and the process default applies. None and False are different answers."""

    @classmethod
    def load(cls, *args: Any, **kwargs: Any) -> "ReactiveComponent":  # type: ignore[misc]
        """Build this component for the current request. Override in subclasses.

        The default builds a field-default instance, so a reactive component
        with nothing to fetch stays valid and the wrap always has a body.
        """
        return cls()

    def state_hash(self) -> str:
        """Return a SHA-256 hex digest of this instance's output-relevant field values.

        Reads nothing but the instance's own fields: no cache lookup and no
        ``load()`` call, so it is safe to call at any point in a render.
        """
        exclude = getattr(type(self), "state_hash_exclude", frozenset({"id"}))
        payload = self.model_dump(mode="json", exclude=set(exclude))
        # JSON-mode dump plus sorted, separator-pinned encoding so that dict
        # ordering and non-JSON-native types can't perturb an unchanged state.
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def __init_subclass__(
        cls,
        *,
        react: Iterable[object] = (),
        cache: CachePolicy | Literal[False] | None = None,
        **kwargs: Any,
    ) -> None:
        """Consume the ``react`` and ``cache`` class kwargs and record them.

        Both are recorded on every subclass rather than inherited: a subclass
        declares its own dependencies and its own caching, and silently reusing
        a parent's would tie its cache entry to state it never reads.
        """
        cls._pjx_react_keys = tuple(coerce_reactive_key(key) for key in react or ())
        # Stored exactly as given: an omitted cache= is None, which means "no
        # answer, use the process default" and is not the same as an explicit
        # False. Resolving None against the default belongs to whoever reads it.
        cls._pjx_cache_policy = cache
        super().__init_subclass__(**kwargs)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Run BaseComponent's registration, resolve the key field, install the wrap."""
        super().__pydantic_init_subclass__(**kwargs)
        cls._pjx_key_field = resolve_pjx_key_field(cls)
        cls._pjx_key_adapter = _build_key_adapter(cls)
        if "load" not in cls.__dict__:
            # cls inherits load unchanged: the ancestor that defines it already
            # validated and wrapped it. Re-running _unwrap_load here would grab
            # the already-wrapped function (not a raw user def) and reject it
            # outright, so skip re-wrapping. This is still safe for cache
            # identity: wrapped_load reads every per-subclass fact (cache key,
            # cache_put, isinstance check, react keys) off the classmethod's
            # bound cls at call time, not off a value closed in when the
            # ancestor was wrapped, so cls.load(...) is correctly keyed to cls
            # even though the wrapper object itself is the ancestor's.
            return
        real_load, is_classmethod = _unwrap_load(cls)
        _validate_load_is_classmethod(cls, real_load, is_classmethod)
        context_param = resolve_load_context_param(real_load)
        _validate_load_params(cls, real_load, context_param)
        _validate_protocol_mode_load_params(cls, real_load, context_param)
        cls.load = classmethod(_wrap_load(cls, real_load, context_param))  # pyright: ignore[reportAttributeAccessIssue]


class PjxKey:
    """Marker for ``Annotated[T, PjxKey()]`` on the field that identifies an instance.

    The marked field's value becomes this instance's load-cache key, so two
    instances standing for the same domain object share one cached ``load()``
    result and instances standing for different ones do not.
    """


def _metadata_has_pjx_key(metadata: Iterable[Any]) -> bool:
    """Report whether a field's metadata list carries the PjxKey marker."""
    return any(isinstance(meta, PjxKey) for meta in metadata)


def _annotation_has_pjx_key(annotation: Any) -> bool:
    """Report whether a raw annotation is ``Annotated[..., PjxKey()]``."""
    if get_origin(annotation) is Annotated:
        return _metadata_has_pjx_key(get_args(annotation)[1:])
    return False


def _field_has_pjx_key(field_info: FieldInfo) -> bool:
    """Report whether a pydantic field carries the marker, either way it survives.

    Pydantic keeps bare ``Annotated`` extras in ``metadata`` but leaves a
    ``Field()``-wrapped annotation reachable only through ``annotation``, so
    both places have to be checked.
    """
    if _metadata_has_pjx_key(field_info.metadata):
        return True
    return _annotation_has_pjx_key(field_info.annotation)


def pjx_key_field_names(model_cls: type[Any]) -> list[str]:
    """Names of every field on a class marked with PjxKey."""
    names = [
        name
        for name, field_info in model_cls.model_fields.items()
        if _field_has_pjx_key(field_info)
    ]
    if names:
        return names
    # Before pydantic populates model_fields the markers are only visible on the
    # raw annotations; under PEP 563 those are strings, so resolve them first
    # and keep the extras.
    try:
        annotations = get_type_hints(model_cls, include_extras=True)
    except (NameError, TypeError, AttributeError):
        annotations = getattr(model_cls, "__annotations__", {})
    return [
        name
        for name, annotation in annotations.items()
        if _annotation_has_pjx_key(annotation)
    ]


def _build_key_adapter(model_cls: type[Any]) -> "TypeAdapter[Any] | None":
    """A validator for the PjxKey field's declared type, built once per class.

    Built at class-definition time, alongside ``_pjx_key_field``, because it is
    a per-class derived fact — the same rule the load wrap and the descriptor
    follow. A class with no PjxKey field, or one whose field carries no
    resolvable annotation, gets None and coerces nothing.
    """
    field = resolve_pjx_key_field(model_cls)
    if field is None:
        return None
    info = model_cls.model_fields.get(field)
    if info is None or info.annotation is None:
        return None
    return TypeAdapter(info.annotation)


def coerce_load_arg(cls: type["ReactiveComponent"], value: object) -> object:
    """A manifest load arg, restored to the type the PjxKey field declares.

    ``data-pjx-load`` is an HTML attribute, so a key declared ``int`` comes
    back off the client as ``"1"``. Handing that straight to ``load()`` would
    break the signature the author wrote against — ``store.get("1")`` misses a
    dict keyed by ``int`` — so the string is validated back to the declared
    type first.

    A value that will not validate is passed through untouched rather than
    raised on: ``load()`` is entitled to reject it with its own error, and the
    fan-out walk turns that into a delete swap.
    """
    adapter = cls._pjx_key_adapter
    if adapter is None or value is None:
        return value
    try:
        return adapter.validate_python(value)
    except ValidationError:
        return value


def resolve_pjx_key_field(model_cls: type[Any]) -> str | None:
    """Return the single PjxKey field's name, or None when the class has none.

    Args:
        model_cls: The ReactiveComponent subclass being defined.

    Returns:
        The field name, or None for an unmarked class.

    Raises:
        TypeError: The class marks more than one field.
    """
    names = pjx_key_field_names(model_cls)
    if not names:
        return None
    if len(names) > 1:
        raise TypeError(
            f"{model_cls.__name__} declares multiple PjxKey fields {names!r}; "
            f"at most one is allowed."
        )
    return names[0]


_MIGRATION_HINT = (
    "load() is now a classmethod factory that returns an instance:\n"
    "    @classmethod\n"
    "    def load(cls, row_id: int) -> 'Row': return cls(row_id=row_id, ...)\n"
    "instead of the old instance method `def load(self) -> None`."
)


def _unwrap_load(cls: type[Any]) -> tuple[Callable[..., Any], bool]:
    """The raw function behind ``cls.load`` and whether it was a classmethod.

    Read off ``__dict__`` rather than ``getattr``: a classmethod accessed
    through the class is already bound, and the binding is exactly the fact
    being tested.
    """
    for klass in cls.__mro__:
        raw = klass.__dict__.get("load")
        if raw is not None:
            return (raw.__func__ if isinstance(raw, classmethod) else raw), isinstance(
                raw, classmethod
            )
    raise TypeError(f"{cls.__name__} has no load()")


def _validate_load_is_classmethod(
    cls: type[Any], func: Callable[..., Any], is_cm: bool
) -> None:
    """Reject an instance-method ``load``, pointing at the migration.

    Raises:
        TypeError: ``load`` is not a classmethod, or its first parameter is not
            ``cls``.
    """
    params = list(inspect.signature(func).parameters)
    if not is_cm or not params or params[0] != "cls":
        raise TypeError(
            f"{cls.__name__}.load must be a @classmethod whose first parameter "
            f"is `cls`. {_MIGRATION_HINT}"
        )


def _load_value_params(
    func: Callable[..., Any], context_param: str | None
) -> list[str]:
    """``load``'s parameters minus ``cls`` and the app-context one.

    Uses ``inspect.signature`` and never ``get_type_hints``: this runs while the
    class is still being built, where a self-referencing return annotation is an
    unresolvable forward ref (#713).
    """
    names = [name for name in inspect.signature(func).parameters if name != "cls"]
    if context_param is not None and context_param in names:
        names.remove(context_param)
    return names


def _validate_load_params(
    cls: type[Any], func: Callable[..., Any], context_param: str | None
) -> None:
    """Check ``load``'s parameters against the class's PjxKey field names.

    Strict by default: the parameter list must be exactly the key fields. Under
    ``extra="allow"`` the key fields are a required minimum only — anything
    beyond them is the class's own protocol, so it is not checked.

    Raises:
        TypeError: The parameters do not satisfy the class's key fields.
    """
    expected = pjx_key_field_names(cls)
    given = _load_value_params(func, context_param)
    if cls.model_config.get("extra") == "allow":
        missing = [name for name in expected if name not in given]
        if missing:
            raise TypeError(
                f"{cls.__name__}.load must accept its PjxKey field(s) {missing!r}; "
                f"it declares {given!r}."
            )
        return
    if not expected:
        if given:
            raise TypeError(
                f"{cls.__name__} declares no PjxKey field, so load() must take no "
                f"parameters beyond cls; it declares {given!r}."
            )
        return
    if given != expected:
        extra = [name for name in given if name not in expected]
        missing = [name for name in expected if name not in given]
        raise TypeError(
            f"{cls.__name__}.load parameters must be exactly its PjxKey fields "
            f"{expected!r}; got {given!r} (missing {missing!r}, extra {extra!r})."
        )


_DETERMINISTIC_REPR_TYPES = (str, int, float, bool, type(None))
"""Types whose repr() is a stable function of the value alone."""

_BARE_CONTAINERS = (list, tuple, set, frozenset, dict)
"""Unparameterized containers: element types unknown, so undecidable."""


def _annotation_reprs_deterministically(annotation: Any) -> bool:
    """Report whether values of this annotation repr() the same for equal values.

    Containers are judged by their arguments: sorting entries by parameter name
    and repr-ing each value never depends on a container's internal ordering
    beyond what repr() itself shows, so ``list[str]`` is fine while a bare
    ``list`` (unknown element types) is not.
    """
    if (
        annotation is inspect.Parameter.empty
        or annotation is Any
        or annotation is object
    ):
        return False
    if annotation is None:
        return True
    if get_origin(annotation) is Annotated:
        return _annotation_reprs_deterministically(get_args(annotation)[0])
    args = [arg for arg in get_args(annotation) if arg is not Ellipsis]
    if args:
        return all(_annotation_reprs_deterministically(arg) for arg in args)
    if not isinstance(annotation, type):
        return False
    if annotation in _DETERMINISTIC_REPR_TYPES or issubclass(annotation, Enum):
        return True
    if get_origin(annotation) is not None or annotation in _BARE_CONTAINERS:
        return False
    # object.__repr__ prints the instance's memory address, so two equal values
    # of such a class stringify differently between processes and even between
    # objects in one process.
    return annotation.__repr__ is not object.__repr__


def _validate_protocol_mode_load_params(
    cls: type[Any], func: Callable[..., Any], context_param: str | None
) -> None:
    """Reject a protocol-mode class whose load args cannot be keyed on.

    Under ``extra="allow"`` every bound argument goes into the cache key, so an
    argument whose repr() carries an identity would key two equal calls apart
    and one changed call together. That is a wrong cache, not a slow one, so it
    is refused when the class is defined rather than discovered at runtime.

    Raises:
        TypeError: A load parameter's type does not serialize deterministically.
    """
    if cls.model_config.get("extra") != "allow":
        return
    signature = inspect.signature(func)
    try:
        hints = get_type_hints(func, include_extras=True)
    except Exception:  # noqa: BLE001 -- an unresolvable forward ref (#713) must
        # not stop a class from being defined; fall back to raw annotations and
        # skip anything still a string.
        hints = {}
    offenders: list[tuple[str, Any]] = []
    for name, param in signature.parameters.items():
        if name in ("cls", context_param):
            continue
        annotation = hints.get(name, param.annotation)
        if isinstance(annotation, str):
            continue
        if not _annotation_reprs_deterministically(annotation):
            offenders.append((name, annotation))
    if offenders:
        detail = ", ".join(
            f"{name!r} ({annotation!r})" for name, annotation in offenders
        )
        raise TypeError(
            f"{cls.__name__}.load parameter(s) {detail} do not serialize "
            f"deterministically for tier-2 cache keys; use a type with a stable "
            f"repr (str, int, float, bool, None, an Enum, or a container of them)."
        )


def _wrap_load(
    cls: type["ReactiveComponent"],
    real_load: Callable[..., Any],
    context_param: str | None,
) -> Callable[[Any], Any]:
    """Build the memoizing wrapper around one class's ``load``.

    Called once per class definition; each call of the returned function only
    builds this instance's cache key and does the get/call/put dance. Outside a
    request scope the cache reads miss and the writes vanish, so the real body
    simply runs every time - no special case is needed here for that.

    Args:
        cls: The subclass being defined.
        real_load: The undecorated function behind ``load``.
        context_param: The app-context parameter's name, pre-resolved by the
            caller so this stays a pure per-call cache dance.
    """

    full_signature = inspect.signature(real_load)
    # The public signature callers bind against excludes the context param:
    # it is injected from the request scope, never passed in by a caller, so
    # binding against the full signature would demand it as a required arg.
    if context_param is not None:
        signature = full_signature.replace(
            parameters=[
                param
                for name, param in full_signature.parameters.items()
                if name != context_param
            ]
        )
    else:
        signature = full_signature

    def wrapped_load(bound_cls: type[Any], *args: Any, **kwargs: Any) -> Any:
        # bound_cls, not the closed-over cls, drives every per-subclass fact
        # below: a subclass that inherits load() unchanged reuses this same
        # wrapper (attribute lookup rebinds bound_cls to it, since it's still
        # a classmethod on the ancestor), so keying off the closed-over cls
        # would silently attribute its cache entries and result type to the
        # ancestor instead.
        bound = signature.bind(bound_cls, *args, **kwargs)
        bound.apply_defaults()
        supplied = dict(bound.arguments)
        supplied.pop("cls", None)
        if context_param is not None:
            supplied.pop(context_param, None)
        cache_key_protocol_mode = bound_cls.model_config.get("extra") == "allow"
        key = _cache_key(bound_cls, supplied, protocol_mode=cache_key_protocol_mode)
        if cache_has(bound_cls, key):
            return cache_get(bound_cls, key)
        call_kwargs = dict(supplied)
        if context_param is not None:
            call_kwargs[context_param] = get_load_context()
        result = real_load(bound_cls, **call_kwargs)
        if not isinstance(result, bound_cls):
            raise TypeError(
                f"{bound_cls.__name__}.load must return an instance of "
                f"{bound_cls.__name__}; got {type(result).__name__}."
            )
        # Index under both the static react keys (a bare "todos" dirties every
        # instance) and, when this call has a load key, the per-instance
        # "todos:1" composite reactive_key() produces — @mutates(key=...) and
        # dirty(reactive_key(...)) dirty only the composite, so invalidate()
        # needs both forms to find this entry.
        react_keys = bound_cls._pjx_react_keys
        field = bound_cls._pjx_key_field
        load_key = coerce_load_key_str(supplied.get(field)) if field else None
        if load_key is not None:
            react_keys = (
                *react_keys,
                *(f"{rk}:{load_key}" for rk in bound_cls._pjx_react_keys),
            )
        cache_put(bound_cls, key, result, react_keys=react_keys)
        return result

    return wrapped_load


def _cache_key(
    cls: type["ReactiveComponent"], supplied: dict[str, Any], *, protocol_mode: bool
) -> object:
    """This call's cache key: the key-field value, or every bound argument.

    Under ``extra="allow"`` the extra parameters are part of what was asked
    for, so two calls that differ only there must not collide; strict mode has
    nothing but the key field to distinguish calls by, and keeping its key the
    plain coerced string leaves fanout's ``_load_key()`` derivation intact.
    """
    if protocol_mode:
        return tuple(sorted((name, repr(value)) for name, value in supplied.items()))
    field = cls._pjx_key_field
    if field is None:
        return None
    return coerce_load_key_str(supplied.get(field))


_KEY_SCHEMA_VERSION = "1"
"""Schema version baked into every string cache key. Bump it whenever the key's
meaning changes, so an upgraded pyjinhx never serves entries a previous version
wrote under different semantics."""

_NO_LOAD_KEY = "-"
"""String-key segment for a class with no PjxKey field. Safe against collision
with a real key value of "-": the key already carries the class's module and
qualname, and a given class either has a key field or has none."""

_STRING_KEY_MAX_PLAIN = 256
"""Plain-form length above which the protocol-mode load key is hashed instead."""


def _string_cache_key(
    cls: type["ReactiveComponent"], supplied: dict[str, Any], *, protocol_mode: bool
) -> str:
    """Build the versioned string form of this call's cache key.

    Shape: ``pjx:<version>:<module>.<qualname>:<load_key>``. Derived from the
    same ``_cache_key()`` value tier 1 keys on, so the two tiers can never
    disagree about what identifies a call.
    """
    key = _cache_key(cls, supplied, protocol_mode=protocol_mode)
    if protocol_mode:
        pairs = cast(tuple[tuple[str, str], ...], key)
        # _cache_key() already sorted by name, so equal arguments passed in a
        # different keyword order serialize to the same string.
        plain = ",".join(f"{name}={value}" for name, value in pairs)
        if len(plain) > _STRING_KEY_MAX_PLAIN:
            load_key = hashlib.sha256(plain.encode("utf-8")).hexdigest()
        else:
            load_key = plain
    else:
        str_key = cast(str | None, key)
        # `is None`, not `or`: a real load-key value that happens to be falsy
        # (e.g. an empty-string PjxKey field) must not be conflated with "this
        # class has no PjxKey field at all" — both would otherwise collapse to
        # the same placeholder segment and collide.
        load_key = _NO_LOAD_KEY if str_key is None else str_key
    return f"pjx:{_KEY_SCHEMA_VERSION}:{cls.__module__}.{cls.__qualname__}:{load_key}"

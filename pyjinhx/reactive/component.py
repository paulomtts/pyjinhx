"""ReactiveComponent: a component whose ``load()`` is memoized per request.

The wrap is installed once, when the subclass is defined, and rebound onto the
class exactly like the ClassDescriptor is - per-class derived facts are computed
at registration, never per render.
"""

import hashlib
import inspect
import json
from collections.abc import Callable, Iterable
from typing import Annotated, Any, ClassVar, get_args, get_origin, get_type_hints

from pydantic.fields import FieldInfo

from pyjinhx.app_context import resolve_load_context_param
from pyjinhx.component import BaseComponent
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

    state_hash_exclude: ClassVar[frozenset[str]] = frozenset({"id"})
    """Field names left out of the state hash. A subclass's value replaces this
    one outright rather than adding to it."""

    @classmethod
    def load(cls) -> "ReactiveComponent":
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

    def pjx_mount(self) -> None:
        """Populate this instance from the cache-routed ``load()`` factory.

        A shim: rendering.py still constructs a child and then mounts it, so
        the factory's result is copied onto the instance that already exists.
        #727 rewires ``_fill_children`` to call ``Cls.load(**key_args)``
        directly and deletes this hook.
        """
        cls = type(self)
        field = cls._pjx_key_field
        loaded = cls.load(**({field: getattr(self, field)} if field else {}))
        names = list(cls.model_fields) + list(loaded.__pydantic_extra__ or ())
        for name in names:
            if name != "id":
                setattr(self, name, getattr(loaded, name))

    def __init_subclass__(cls, *, react: Iterable[object] = (), **kwargs: Any) -> None:
        """Consume the ``react`` class kwarg and record it as normalized keys.

        Recorded on every subclass rather than inherited: a subclass declares
        its own dependencies, and silently reusing a parent's set would tie its
        cache entry to state it never reads.
        """
        cls._pjx_react_keys = tuple(coerce_reactive_key(key) for key in react or ())
        super().__init_subclass__(**kwargs)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Run BaseComponent's registration, resolve the key field, install the wrap."""
        super().__pydantic_init_subclass__(**kwargs)
        cls._pjx_key_field = resolve_pjx_key_field(cls)
        if "load" not in cls.__dict__:
            # cls inherits load unchanged: the ancestor that defines it already
            # validated and wrapped it, closing over *that* ancestor's cls for
            # cache-key derivation. Re-running _unwrap_load here would grab the
            # already-wrapped function (not a raw user def) and either reject
            # it outright or, worse, rewrap with the wrong cls closed in,
            # silently mis-keying this subclass's cache entries under the
            # ancestor's identity.
            return
        real_load, is_classmethod = _unwrap_load(cls)
        _validate_load_is_classmethod(cls, real_load, is_classmethod)
        context_param = resolve_load_context_param(real_load)
        _validate_load_params(cls, real_load, context_param)
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
    protocol_mode = cls.model_config.get("extra") == "allow"
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
        bound = signature.bind(bound_cls, *args, **kwargs)
        bound.apply_defaults()
        supplied = dict(bound.arguments)
        supplied.pop("cls", None)
        if context_param is not None:
            supplied.pop(context_param, None)
        key = _cache_key(cls, supplied, protocol_mode=protocol_mode)
        if cache_has(cls, key):
            return cache_get(cls, key)
        call_kwargs = dict(supplied)
        if context_param is not None:
            call_kwargs[context_param] = get_load_context()
        result = real_load(bound_cls, **call_kwargs)
        if not isinstance(result, cls):
            raise TypeError(
                f"{cls.__name__}.load must return an instance of {cls.__name__}; "
                f"got {type(result).__name__}."
            )
        # Index under both the static react keys (a bare "todos" dirties every
        # instance) and, when this call has a load key, the per-instance
        # "todos:1" composite reactive_key() produces — @mutates(key=...) and
        # dirty(reactive_key(...)) dirty only the composite, so invalidate()
        # needs both forms to find this entry.
        react_keys = cls._pjx_react_keys
        field = cls._pjx_key_field
        load_key = coerce_load_key_str(supplied.get(field)) if field else None
        if load_key is not None:
            react_keys = (
                *react_keys,
                *(f"{rk}:{load_key}" for rk in cls._pjx_react_keys),
            )
        cache_put(cls, key, result, react_keys=react_keys)
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

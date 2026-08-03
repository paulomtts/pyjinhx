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
        """Run the cache-routed ``load()`` before this instance's recursive render.

        Overrides BaseComponent's no-op: rendering.py calls this hook on every
        child it instantiates from a ChildRef without knowing anything about
        ReactiveComponent, so mounting a reactive child never needs a manual
        ``load()`` call from the template author.
        """
        self.load()

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
        cls.load = classmethod(_wrap_load(cls, real_load))  # pyright: ignore[reportAttributeAccessIssue]


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


def _validate_load_is_classmethod(cls: type[Any], func: Callable[..., Any], is_cm: bool) -> None:
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


def _wrap_load(
    cls: type["ReactiveComponent"], real_load: Callable[..., Any]
) -> Callable[[Any], Any]:
    """Build the memoizing wrapper around one class's ``load``.

    Called once per class definition; each call of the returned function only
    builds this instance's cache key and does the get/call/put dance. Outside a
    request scope the cache reads miss and the writes vanish, so the real body
    simply runs every time - no special case is needed here for that.

    The app-context parameter, if the signature declares one, is resolved here
    too and closed over: signature introspection is a per-class fact, and doing
    it on every load() would put it on the hot render path.

    Raises:
        TypeError: ``load`` declares more than one app-context parameter.
    """
    context_param = resolve_load_context_param(real_load)

    def wrapped_load(self: Any) -> Any:
        # An unmarked class has no per-instance key, so all its instances keep
        # sharing the one entry under the null key.
        field = cls._pjx_key_field
        key = coerce_load_key_str(getattr(self, field, None)) if field else None
        if cache_has(cls, key):
            return cache_get(cls, key)
        if context_param is None:
            result = real_load(self)
        else:
            result = real_load(self, **{context_param: get_load_context()})
        # Index under both the static react keys (a bare "todos" dirties every
        # instance) and, when this instance has a load key, the per-instance
        # "todos:1" composite form reactive_key() produces — @mutates(key=...)
        # and dirty(reactive_key(...)) dirty only the composite, never the bare
        # key alongside it, so invalidate() needs both forms to find this entry.
        react_keys = cls._pjx_react_keys
        if key is not None:
            react_keys = (*react_keys, *(f"{rk}:{key}" for rk in cls._pjx_react_keys))
        cache_put(cls, key, result, react_keys=react_keys)
        return result

    return wrapped_load

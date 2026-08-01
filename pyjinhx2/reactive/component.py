"""ReactiveComponent: a component whose ``load()`` is memoized per request.

The wrap is installed once, when the subclass is defined, and rebound onto the
class exactly like the ClassDescriptor is - per-class derived facts are computed
at registration, never per render.
"""

from collections.abc import Callable, Iterable
from typing import Annotated, Any, ClassVar, get_args, get_origin, get_type_hints

from pydantic.fields import FieldInfo

from pyjinhx2.component import BaseComponent
from pyjinhx2.reactive.cache import cache_get, cache_has, cache_put
from pyjinhx2.reactive.keys import coerce_load_key_str, coerce_reactive_key


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

    def load(self) -> Any:
        """Fetch this component's data. Override in subclasses.

        The default does nothing, so a reactive component that has no data to
        fetch stays valid and the wrap always has a body to call.
        """
        return None

    def pjx_mount(self) -> None:
        """Run the cache-routed ``load()`` before this instance's recursive render.

        Overrides BaseComponent's no-op: render.py calls this hook on every
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
        cls.load = _wrap_load(cls, cls.load)  # pyright: ignore[reportAttributeAccessIssue]


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


def _wrap_load(
    cls: type["ReactiveComponent"], real_load: Callable[[Any], Any]
) -> Callable[[Any], Any]:
    """Build the memoizing wrapper around one class's ``load``.

    Called once per class definition; each call of the returned function only
    builds this instance's cache key and does the get/call/put dance. Outside a
    request scope the cache reads miss and the writes vanish, so the real body
    simply runs every time - no special case is needed here for that.
    """

    def wrapped_load(self: Any) -> Any:
        # An unmarked class has no per-instance key, so all its instances keep
        # sharing the one entry under the null key.
        field = cls._pjx_key_field
        key = coerce_load_key_str(getattr(self, field, None)) if field else None
        if cache_has(cls, key):
            return cache_get(cls, key)
        result = real_load(self)
        cache_put(cls, key, result, react_keys=cls._pjx_react_keys)
        return result

    return wrapped_load

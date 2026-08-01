"""ReactiveComponent: a component whose ``load()`` is memoized per request.

The wrap is installed once, when the subclass is defined, and rebound onto the
class exactly like the ClassDescriptor is - per-class derived facts are computed
at registration, never per render.
"""

from collections.abc import Callable, Iterable
from typing import Any

from pyjinhx2.component import BaseComponent
from pyjinhx2.reactive.cache import cache_get, cache_has, cache_put
from pyjinhx2.reactive.keys import coerce_reactive_key


class ReactiveComponent(BaseComponent):
    """Base for components that fetch their data in ``load()``.

    Every subclass's ``load()`` is routed through the request-scoped load cache:
    the first call in a request runs the real body, later calls in that same
    request reuse its result. Declaring ``react=(...)`` on the subclass reverse-
    indexes the cached result under those keys, so dirtying one evicts it.
    """

    _pjx_react_keys: tuple[str, ...] = ()
    """Normalized reactive keys this class's cached load result depends on."""

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
        """Run BaseComponent's registration, then install the load wrap."""
        super().__pydantic_init_subclass__(**kwargs)
        cls.load = _wrap_load(cls, cls.load)  # pyright: ignore[reportAttributeAccessIssue]


def _wrap_load(cls: type, real_load: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Build the memoizing wrapper around one class's ``load``.

    Called once per class definition; each call of the returned function only
    does the cache get/call/put dance. Outside a request scope the cache reads
    miss and the writes vanish, so the real body simply runs every time - no
    special case is needed here for that.
    """

    def wrapped_load(self: Any) -> Any:
        # Instance-level load keys do not exist yet, so every instance of a
        # class shares one entry under the null key.
        key = None
        if cache_has(cls, key):
            return cache_get(cls, key)
        result = real_load(self)
        cache_put(cls, key, result, react_keys=cls._pjx_react_keys)
        return result

    return wrapped_load

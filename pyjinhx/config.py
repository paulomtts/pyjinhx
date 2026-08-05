"""App-level configuration for pyjinhx: the settings object and the setup() entrypoint.

config sits above the render spine and may read from it; nothing in the spine,
in reactive/ or in client/ may import this module back — except session.py's
request_scope(), which reads current_settings() through a function-local
import to seed a default session's Jinja globals/filters, never at module
scope (test_session_only_imports_config_inside_a_function_body pins that).
Siblings that do not exist yet (dev, integrations.fastapi) are imported
lazily inside functions so importing this module never depends on them.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields, replace
from importlib.util import find_spec as _find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pyjinhx._component import BaseComponent
from pyjinhx.discovery import build_registry
from pyjinhx.integrations.base import IntegrationBackend, get_backend

if TYPE_CHECKING:
    # Type-only, and it must stay that way: config sits above reactive/, and
    # naming a backend's protocol in a field annotation must not make importing
    # config drag reactive/ in at runtime.
    from pyjinhx.reactive.backend import CacheBackend

# Sentinel distinguishing "argument omitted" from None or a real value, so
# setup()'s pass-through keywords never clobber an explicit settings object.
_UNSET: Any = object()

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _env_bool(name: str, default: bool) -> bool:
    """``name``'s value as a bool, or ``default`` when it is unset or empty."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    lowered = raw.strip().lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ValueError(
        f"{name}={raw!r} is not a boolean; use one of {sorted(_TRUE | _FALSE)}."
    )


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name)
    return Path(raw) if raw else None


@dataclass(frozen=True)
class PjxSettings:
    """The app-level knobs pyjinhx reads once at startup.

    ``inject_htmx`` is stored only; how it maps onto the session's asset modes
    is pending design. ``jinja_globals`` and ``jinja_filters`` are registered
    onto each request's Jinja environment by the session that reads them.
    """

    reactive_dev: bool = False
    inject_htmx: bool = True
    components_root: Path | str | None = None
    static_root: Path | str | None = None
    # None rather than an empty dict: the dataclass is frozen and a mutable
    # default is disallowed outright, and "nothing to add" is exactly what a
    # missing mapping should mean to the session that applies these.
    jinja_globals: Mapping[str, Any] | None = None
    jinja_filters: Mapping[str, Any] | None = None
    # Handed in by the app, never read from the environment: a backend needs a
    # path, a connection or a constructor call that a string cannot carry.
    cache_backend: CacheBackend | None = None

    @classmethod
    def from_env(cls) -> PjxSettings:
        """Settings read from the ``PJX_*`` environment variables."""
        return cls(
            reactive_dev=_env_bool("PJX_REACTIVE_DEV", False),
            inject_htmx=_env_bool("PJX_INJECT_HTMX", True),
            components_root=_env_path("PJX_COMPONENTS_ROOT"),
            static_root=_env_path("PJX_STATIC_ROOT"),
        )

    def merge(self, **overrides: Any) -> PjxSettings:
        """A copy of these settings with ``overrides`` applied.

        Keywords carrying the ``_UNSET`` sentinel are dropped, so a caller can
        pass every field through unconditionally and still say nothing about
        the ones it was never given. ``None`` is a real value and does override.
        """
        known = {field.name for field in fields(self)}
        unknown = sorted(set(overrides) - known)
        if unknown:
            raise TypeError(f"unknown pyjinhx settings: {unknown}")
        applied = {
            key: value for key, value in overrides.items() if value is not _UNSET
        }
        return replace(self, **applied)


_current = PjxSettings()


def current_settings() -> PjxSettings:
    """The settings the last ``configure_pyjinhx`` published for this process."""
    return _current


def _apply_reactive_dev(enabled: bool) -> None:
    """Turn dev mode on or off, if the dev module is importable.

    The import is deferred and its absence is not an error: configuration must
    still succeed in an install where dev tooling is not present, with the flag
    recorded for whoever reads it later.
    """
    try:
        from pyjinhx import dev  # pyright: ignore[reportAttributeAccessIssue]
    except ImportError:
        return
    if dev is None:
        return
    if enabled:
        dev.enable_reactive_dev()
    else:
        dev.disable_reactive_dev()


def configure_pyjinhx(settings: PjxSettings) -> PjxSettings:
    """Publish ``settings`` as this process's configuration and apply its effects."""
    global _current
    _current = settings
    _apply_reactive_dev(settings.reactive_dev)
    return settings


def shutdown_pyjinhx() -> None:
    """Reset the process back to default settings and undo what config applied."""
    global _current
    _current = PjxSettings()
    _apply_reactive_dev(False)


def setup(
    app: object | None = None,
    *,
    settings: PjxSettings | None = None,
    context_factory: Callable[[Any], object | None] | None = None,
    components_root: Path | str | None = _UNSET,
    static_root: Path | str | None = _UNSET,
    **kwargs: Any,
) -> PjxSettings:
    """Configure pyjinhx for this process, and optionally wire it into an app.

    Resolution order: an explicit ``settings`` object replaces the environment
    as the base, and explicit keywords override whichever base was used.
    ``components_root`` also triggers component discovery. With ``app=None``
    only process configuration runs, which is what tests and scripts want.
    """
    base = settings if settings is not None else PjxSettings.from_env()
    resolved = base.merge(
        components_root=components_root,
        static_root=static_root,
        **kwargs,
    )
    _register_components(resolved.components_root)
    configure_pyjinhx(resolved)
    if app is None:
        return resolved
    backend = _load_backend()
    if not backend.accepts(app):  # pyright: ignore[reportAttributeAccessIssue]
        raise TypeError(
            "setup(app=...) needs a Starlette/FastAPI-like app with "
            "add_middleware and router attributes."
        )
    from pyjinhx.integrations.fastapi import (  # pyright: ignore[reportMissingImports]
        apply_setup,
    )

    apply_setup(app, resolved, context_factory=context_factory)  # pyright: ignore[reportArgumentType]
    return resolved


def _load_backend() -> IntegrationBackend:
    """The framework adapter ``setup(app=...)`` wires through.

    An already-registered backend wins outright: importing an adapter is how a
    backend normally gets registered, so a caller that registered its own would
    otherwise be overruled by whatever the fastapi probe finds.

    The distribution is probed with find_spec rather than caught as an
    ImportError from the adapter: a genuine bug inside the adapter would
    otherwise be reported to the caller as a missing extra.
    """
    registered = get_backend()
    if registered is not None:
        return registered

    if _find_spec("fastapi") is None:
        raise ImportError(
            "setup(app=...) needs a web framework adapter, and none is "
            "installed. Install the extra: pip install 'pyjinhx[fastapi]'."
        )
    import pyjinhx.integrations.fastapi  # noqa: F401  # registers the backend

    backend = get_backend()
    assert backend is not None, "importing the adapter must register a backend"
    return backend


def _force_load_builtins() -> None:
    """Eagerly import every shipped builtin, if the package has been imported.

    ``pyjinhx.builtins`` exposes its classes lazily (#701) to keep import-time
    cost down: a bare ``import pyjinhx.builtins`` defines no component classes
    at all, it only makes each one importable on first attribute access.
    Discovery can only claim a tag for a class that already exists, so without
    this step a builtin would stay unregistered until something happened to
    touch that one name. Walking the package's own lazy-import table forces
    every builtin's module to load, once, without the app having to name each
    one itself — and does nothing when the app never imported the package.
    """
    builtins_module = sys.modules.get("pyjinhx.builtins")
    if builtins_module is None:
        return
    lazy_imports = getattr(builtins_module, "_lazy_imports", None)
    if not lazy_imports:
        return
    for name in lazy_imports:
        getattr(builtins_module, name)


def _register_components(components_root: Path | str | None) -> None:
    """Publish the tag -> class registry for this process.

    ``components_root`` is walked when there is one; classes that already
    carry their own template on disk — every shipped builtin — claim their
    tags either way, so an app with no components of its own still gets them.
    """
    _force_load_builtins()
    build_registry(components_root, _all_component_classes())


def _all_component_classes() -> list[type]:
    """Every declared BaseComponent subclass, nested ones included."""
    found: list[type] = []
    stack = list(BaseComponent.__subclasses__())
    while stack:
        cls = stack.pop()
        found.append(cls)
        stack.extend(cls.__subclasses__())
    return found

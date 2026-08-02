"""App-level configuration for pyjinhx2: the settings object and the setup() entrypoint.

config sits above the render spine and may read from it; nothing in the spine,
in reactive/ or in client/ may import this module back. Siblings that do not
exist yet (dev, integrations.fastapi) are imported lazily inside functions so
importing this module never depends on them.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

from pyjinhx2.component import BaseComponent
from pyjinhx2.discovery import build_registry

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
    """The app-level knobs pyjinhx2 reads once at startup.

    ``inject_htmx`` is stored only; how it maps onto the session's asset modes
    is pending design.
    """

    reactive_dev: bool = False
    inject_htmx: bool = True
    components_root: Path | str | None = None
    static_root: Path | str | None = None

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
        from pyjinhx2 import dev  # pyright: ignore[reportAttributeAccessIssue]
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
    """Configure pyjinhx2 for this process, and optionally wire it into an app.

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
    if resolved.components_root is not None:
        _register_components(resolved.components_root)
    configure_pyjinhx(resolved)
    if app is None:
        return resolved
    if not _is_asgi_app(app):
        raise TypeError(
            "setup(app=...) needs a Starlette/FastAPI-like app with "
            "add_middleware and router attributes."
        )
    from pyjinhx2.integrations.fastapi import (  # pyright: ignore[reportMissingImports]
        apply_setup,
    )

    apply_setup(app, resolved, context_factory=context_factory)  # pyright: ignore[reportArgumentType]
    return resolved


def _is_asgi_app(app: object) -> bool:
    """Whether ``app`` looks like a Starlette/FastAPI application.

    Duck-typed rather than isinstance-checked so pyjinhx2 never imports
    Starlette to answer a question about an object the caller already built.
    """
    return hasattr(app, "add_middleware") and hasattr(app, "router")


def _register_components(components_root: Path | str) -> None:
    """Walk ``components_root`` and publish the tag -> class registry.

    Every declared component class is offered to the walk; discovery is what
    decides which of them a template on disk actually claims.
    """
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

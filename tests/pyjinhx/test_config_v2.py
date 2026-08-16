"""Unit tests for pyjinhx/config.py — PjxSettings, setup() and the process-wide holder."""

import dataclasses
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import pyjinhx
from pyjinhx.config import PjxSettings
from pyjinhx.reactive.backend import InMemoryCacheBackend


@pytest.fixture(autouse=True)
def _reset_process_settings():
    yield
    from pyjinhx.config import shutdown_pyjinhx

    shutdown_pyjinhx()


def test_defaults():
    settings = PjxSettings()
    assert settings.reactive_dev is False
    assert settings.inject_htmx is True
    assert settings.components_root is None
    assert settings.static_root is None
    assert settings.jinja_globals is None
    assert settings.jinja_filters is None


def test_jinja_globals_and_filters_are_stored_as_given():
    def shout(value: str) -> str:
        return value.upper()

    settings = PjxSettings(jinja_globals={"x": 1}, jinja_filters={"shout": shout})
    assert settings.jinja_globals == {"x": 1}
    assert settings.jinja_filters == {"shout": shout}


def test_settings_are_frozen():
    settings = PjxSettings()
    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.reactive_dev = True  # type: ignore[misc]


def test_from_env_reads_every_var(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PJX_REACTIVE_DEV", "true")
    monkeypatch.setenv("PJX_INJECT_HTMX", "0")
    monkeypatch.setenv("PJX_COMPONENTS_ROOT", "/srv/components")
    monkeypatch.setenv("PJX_STATIC_ROOT", "/srv/static")
    settings = PjxSettings.from_env()
    assert settings.reactive_dev is True
    assert settings.inject_htmx is False
    assert settings.components_root == Path("/srv/components")
    assert settings.static_root == Path("/srv/static")


def test_from_env_falls_back_to_defaults(monkeypatch: pytest.MonkeyPatch):
    for name in (
        "PJX_REACTIVE_DEV",
        "PJX_INJECT_HTMX",
        "PJX_COMPONENTS_ROOT",
        "PJX_STATIC_ROOT",
    ):
        monkeypatch.delenv(name, raising=False)
    assert PjxSettings.from_env() == PjxSettings()


def test_from_env_rejects_a_non_bool_string(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PJX_REACTIVE_DEV", "maybe")
    with pytest.raises(ValueError, match="PJX_REACTIVE_DEV"):
        PjxSettings.from_env()


def test_merge_with_no_arguments_changes_nothing():
    settings = PjxSettings(reactive_dev=True, components_root=Path("/a"))
    assert settings.merge() == settings


def test_merge_only_overrides_what_was_passed():
    settings = PjxSettings(reactive_dev=True, inject_htmx=False)
    merged = settings.merge(components_root=Path("/a"))
    assert merged.components_root == Path("/a")
    assert merged.reactive_dev is True
    assert merged.inject_htmx is False


def test_merge_drops_unset_sentinel_values():
    from pyjinhx.config import _UNSET

    settings = PjxSettings(reactive_dev=True)
    assert settings.merge(reactive_dev=_UNSET, inject_htmx=_UNSET) == settings


def test_merge_accepts_none_as_a_real_value():
    settings = PjxSettings(components_root=Path("/a"))
    assert settings.merge(components_root=None).components_root is None


def test_configure_then_shutdown_round_trip():
    from pyjinhx.config import configure_pyjinhx, current_settings, shutdown_pyjinhx

    configure_pyjinhx(PjxSettings(reactive_dev=True, inject_htmx=False))
    assert current_settings().reactive_dev is True
    assert current_settings().inject_htmx is False
    shutdown_pyjinhx()
    assert current_settings() == PjxSettings()


def test_reactive_dev_survives_a_missing_dev_module(monkeypatch: pytest.MonkeyPatch):
    """pyjinhx.dev does not exist yet; configure must store the flag anyway."""
    # `from pyjinhx import dev` resolves via getattr(pyjinhx, "dev") first, so
    # the real module (imported elsewhere in this suite) must also be unbound
    # from the package object, not just removed from sys.modules.
    monkeypatch.delattr(pyjinhx, "dev", raising=False)
    monkeypatch.setitem(sys.modules, "pyjinhx.dev", None)
    from pyjinhx.config import configure_pyjinhx, current_settings

    configure_pyjinhx(PjxSettings(reactive_dev=True))
    assert current_settings().reactive_dev is True


def test_reactive_dev_calls_the_dev_hooks_when_available(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delattr(pyjinhx, "dev", raising=False)
    dev = types.ModuleType("pyjinhx.dev")
    dev.enable_reactive_dev = MagicMock()  # type: ignore[attr-defined]
    dev.disable_reactive_dev = MagicMock()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyjinhx.dev", dev)
    from pyjinhx.config import configure_pyjinhx, shutdown_pyjinhx

    configure_pyjinhx(PjxSettings(reactive_dev=True))
    dev.enable_reactive_dev.assert_called_once_with()  # type: ignore[attr-defined]
    shutdown_pyjinhx()
    dev.disable_reactive_dev.assert_called_once_with()  # type: ignore[attr-defined]


def test_setup_without_an_app_returns_merged_settings():
    from pyjinhx.config import setup

    resolved = setup(reactive_dev=True, inject_htmx=False)
    assert resolved.reactive_dev is True
    assert resolved.inject_htmx is False


def test_setup_publishes_the_resolved_settings():
    from pyjinhx.config import current_settings, setup

    resolved = setup(reactive_dev=True)
    assert current_settings() == resolved


def test_explicit_settings_bypasses_the_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PJX_REACTIVE_DEV", "true")
    monkeypatch.setenv("PJX_INJECT_HTMX", "0")
    from pyjinhx.config import setup

    resolved = setup(settings=PjxSettings())
    assert resolved.reactive_dev is False
    assert resolved.inject_htmx is True


def test_explicit_keywords_win_over_an_explicit_settings_object():
    """Precedence rule: keywords are the caller's most specific statement, so
    they override both the environment and a passed-in settings object."""
    from pyjinhx.config import setup

    resolved = setup(settings=PjxSettings(reactive_dev=False), reactive_dev=True)
    assert resolved.reactive_dev is True


def test_components_root_builds_the_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from pyjinhx import config

    calls: list[tuple[Path | str, list[type]]] = []
    monkeypatch.setattr(
        config,
        "build_registry",
        lambda template_dir, classes: calls.append((template_dir, list(classes))),
    )
    config.setup(components_root=tmp_path)
    assert len(calls) == 1
    assert calls[0][0] == tmp_path


def test_no_components_root_still_builds_the_registry_with_no_walked_dir(
    monkeypatch: pytest.MonkeyPatch,
):
    """Issue #738: builtins claim tags off their own template even with no
    components_root, so the registry build must still run — with
    template_dir=None rather than being skipped outright."""
    from pyjinhx import config

    calls: list[object] = []
    monkeypatch.setattr(
        config,
        "build_registry",
        lambda template_dir, classes: calls.append(template_dir),
    )
    config.setup()
    assert calls == [None]


def test_setup_rejects_a_non_asgi_app():
    from pyjinhx.config import setup

    class NotAnApp:
        pass

    with pytest.raises(TypeError, match="add_middleware"):
        setup(NotAnApp())


def test_setup_delegates_an_asgi_app_to_the_fastapi_integration(
    monkeypatch: pytest.MonkeyPatch,
):
    """#484 owns integrations.fastapi; config only hands the app over to it."""
    integration = types.ModuleType("pyjinhx.integrations.fastapi")
    integration.apply_setup = MagicMock()  # type: ignore[attr-defined]
    package = types.ModuleType("pyjinhx.integrations")
    package.fastapi = integration  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyjinhx.integrations", package)
    monkeypatch.setitem(sys.modules, "pyjinhx.integrations.fastapi", integration)

    from pyjinhx.config import setup

    app = MagicMock(spec=["add_middleware", "router"])
    factory = MagicMock()
    resolved = setup(app, context_factory=factory, reactive_dev=True)

    integration.apply_setup.assert_called_once_with(  # type: ignore[attr-defined]
        app, resolved, context_factory=factory
    )
    assert resolved.reactive_dev is True


def test_deferred_cache_machinery_is_not_ported():
    """ADR 0009/0011: no invalidation backend, hub or cache scope in v2.

    Milestone 10 (#800) reopens that deferral for a cross-request cache: the
    only field it adds here is cache_backend, an opt-in handed in by the app.
    """
    names = {field.name for field in dataclasses.fields(PjxSettings)}
    assert names == {
        "reactive_dev",
        "inject_htmx",
        "components_root",
        "static_root",
        "jinja_globals",
        "jinja_filters",
        "cache_backend",
    }


def test_static_root_is_stored_on_the_settings(tmp_path: Path):
    from pyjinhx.config import setup

    assert setup(static_root=tmp_path).static_root == tmp_path


@pytest.fixture(autouse=True)
def _reset_discovery_registry():
    """Each test starts from an empty published registry and leaves one behind."""
    from pyjinhx import discovery

    discovery._registry.mapping = {}
    discovery._registry.template_dir = None
    yield
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None


def test_setup_registers_builtins_with_a_components_root(tmp_path):
    import pyjinhx.builtins  # noqa: F401
    from pyjinhx import discovery
    from pyjinhx.config import setup

    (tmp_path / "user_page.pjx").write_text("<div>user</div>")
    setup(app=None, components_root=tmp_path)

    cls = discovery.get_class("pjx_card")
    assert cls is not None
    assert cls.__name__ == "PJXCard"


def test_setup_registers_builtins_without_a_components_root():
    import pyjinhx.builtins  # noqa: F401
    from pyjinhx import discovery
    from pyjinhx.config import setup

    setup(app=None, components_root=None)

    assert discovery.get_class("pjx_card") is not None


def test_cache_backend_defaults_to_none():
    assert PjxSettings().cache_backend is None


def test_cache_backend_is_stored_by_identity():
    backend = InMemoryCacheBackend()
    settings = PjxSettings(cache_backend=backend)
    assert settings.cache_backend is backend


def test_from_env_never_sets_a_cache_backend(monkeypatch: pytest.MonkeyPatch):
    """A backend needs a path, a connection or a constructor call, none of which
    an environment variable can carry, so there is deliberately no PJX_ var."""
    monkeypatch.setenv(
        "PJX_CACHE_BACKEND", "pyjinhx.reactive.backend:InMemoryCacheBackend"
    )
    assert PjxSettings.from_env().cache_backend is None


def test_merge_applies_a_cache_backend():
    backend = InMemoryCacheBackend()
    merged = PjxSettings().merge(cache_backend=backend)
    assert merged.cache_backend is backend


def test_merge_without_the_keyword_keeps_the_existing_backend():
    backend = InMemoryCacheBackend()
    settings = PjxSettings(cache_backend=backend)
    assert settings.merge().cache_backend is backend
    assert settings.merge(reactive_dev=True).cache_backend is backend


def test_merge_accepts_none_to_clear_the_backend():
    settings = PjxSettings(cache_backend=InMemoryCacheBackend())
    assert settings.merge(cache_backend=None).cache_backend is None


def test_setup_passes_a_cache_backend_through_to_the_settings():
    from pyjinhx.config import current_settings, setup

    backend = InMemoryCacheBackend()
    resolved = setup(cache_backend=backend)
    assert resolved.cache_backend is backend
    assert current_settings().cache_backend is backend


class ClosableBackend:
    """A CacheBackend that also holds something worth releasing on shutdown."""

    def __init__(self) -> None:
        self.closed = 0

    def get(self, key: str) -> object:
        raise AssertionError("shutdown must not read the backend")

    def put(self, key, value, *, tags, ttl) -> None:
        raise AssertionError("shutdown must not write the backend")

    def evict(self, tags) -> None:
        raise AssertionError("shutdown must not evict")

    def clear(self) -> None:
        raise AssertionError("shutdown must not clear")

    def close(self) -> None:
        self.closed += 1


def test_shutdown_closes_a_backend_that_has_a_close():
    from pyjinhx.config import configure_pyjinhx, shutdown_pyjinhx

    backend = ClosableBackend()
    configure_pyjinhx(PjxSettings(cache_backend=backend))
    shutdown_pyjinhx()
    assert backend.closed == 1


def test_shutdown_clears_the_backend_off_the_settings():
    from pyjinhx.config import configure_pyjinhx, current_settings, shutdown_pyjinhx

    configure_pyjinhx(PjxSettings(cache_backend=ClosableBackend()))
    shutdown_pyjinhx()
    assert current_settings().cache_backend is None


def test_shutdown_does_not_require_a_close_method():
    """CacheBackend is a structural Protocol with no close(): an in-memory
    backend has nothing to release, and shutdown must not assume otherwise."""
    from pyjinhx.config import configure_pyjinhx, shutdown_pyjinhx

    backend = InMemoryCacheBackend()
    assert not hasattr(backend, "close")
    configure_pyjinhx(PjxSettings(cache_backend=backend))
    shutdown_pyjinhx()


def test_shutdown_with_no_backend_configured_still_works():
    from pyjinhx.config import configure_pyjinhx, current_settings, shutdown_pyjinhx

    configure_pyjinhx(PjxSettings(reactive_dev=False))
    shutdown_pyjinhx()
    assert current_settings() == PjxSettings()


def test_shutdown_closes_the_backend_only_once():
    from pyjinhx.config import configure_pyjinhx, shutdown_pyjinhx

    backend = ClosableBackend()
    configure_pyjinhx(PjxSettings(cache_backend=backend))
    shutdown_pyjinhx()
    shutdown_pyjinhx()
    assert backend.closed == 1


def test_setup_registers_a_builtin_tag_when_pyjinhx_builtins_was_never_imported():
    """A fresh interpreter: nothing pre-imports pyjinhx.builtins, so only
    setup()'s own force-load can make a builtin tag resolvable.

    This runs in a subprocess because BaseComponent.__subclasses__() is
    process-global and permanent — other test modules import builtin
    submodules directly, so an in-process test would pass on their leftovers
    whether or not setup() force-loads anything.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from pyjinhx import discovery\n"
                "from pyjinhx.config import setup\n"
                "setup(app=None, components_root=None)\n"
                "assert discovery.get_class('pjx_button') is not None, "
                "'setup() left pjx_button unregistered'\n"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr

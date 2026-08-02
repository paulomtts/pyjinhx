"""Unit tests for pyjinhx2/config.py — PjxSettings, setup() and the process-wide holder."""

import dataclasses
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import pyjinhx2
from pyjinhx2.config import PjxSettings


@pytest.fixture(autouse=True)
def _reset_process_settings():
    yield
    from pyjinhx2.config import shutdown_pyjinhx

    shutdown_pyjinhx()


def test_defaults():
    settings = PjxSettings()
    assert settings.reactive_dev is False
    assert settings.inject_htmx is True
    assert settings.components_root is None
    assert settings.static_root is None


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
    from pyjinhx2.config import _UNSET

    settings = PjxSettings(reactive_dev=True)
    assert settings.merge(reactive_dev=_UNSET, inject_htmx=_UNSET) == settings


def test_merge_accepts_none_as_a_real_value():
    settings = PjxSettings(components_root=Path("/a"))
    assert settings.merge(components_root=None).components_root is None


def test_configure_then_shutdown_round_trip():
    from pyjinhx2.config import configure_pyjinhx, current_settings, shutdown_pyjinhx

    configure_pyjinhx(PjxSettings(reactive_dev=True, inject_htmx=False))
    assert current_settings().reactive_dev is True
    assert current_settings().inject_htmx is False
    shutdown_pyjinhx()
    assert current_settings() == PjxSettings()


def test_reactive_dev_survives_a_missing_dev_module(monkeypatch: pytest.MonkeyPatch):
    """pyjinhx2.dev does not exist yet; configure must store the flag anyway."""
    # `from pyjinhx2 import dev` resolves via getattr(pyjinhx2, "dev") first, so
    # the real module (imported elsewhere in this suite) must also be unbound
    # from the package object, not just removed from sys.modules.
    monkeypatch.delattr(pyjinhx2, "dev", raising=False)
    monkeypatch.setitem(sys.modules, "pyjinhx2.dev", None)
    from pyjinhx2.config import configure_pyjinhx, current_settings

    configure_pyjinhx(PjxSettings(reactive_dev=True))
    assert current_settings().reactive_dev is True


def test_reactive_dev_calls_the_dev_hooks_when_available(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delattr(pyjinhx2, "dev", raising=False)
    dev = types.ModuleType("pyjinhx2.dev")
    dev.enable_reactive_dev = MagicMock()  # type: ignore[attr-defined]
    dev.disable_reactive_dev = MagicMock()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyjinhx2.dev", dev)
    from pyjinhx2.config import configure_pyjinhx, shutdown_pyjinhx

    configure_pyjinhx(PjxSettings(reactive_dev=True))
    dev.enable_reactive_dev.assert_called_once_with()  # type: ignore[attr-defined]
    shutdown_pyjinhx()
    dev.disable_reactive_dev.assert_called_once_with()  # type: ignore[attr-defined]


def test_setup_without_an_app_returns_merged_settings():
    from pyjinhx2.config import setup

    resolved = setup(reactive_dev=True, inject_htmx=False)
    assert resolved.reactive_dev is True
    assert resolved.inject_htmx is False


def test_setup_publishes_the_resolved_settings():
    from pyjinhx2.config import current_settings, setup

    resolved = setup(reactive_dev=True)
    assert current_settings() == resolved


def test_explicit_settings_bypasses_the_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PJX_REACTIVE_DEV", "true")
    monkeypatch.setenv("PJX_INJECT_HTMX", "0")
    from pyjinhx2.config import setup

    resolved = setup(settings=PjxSettings())
    assert resolved.reactive_dev is False
    assert resolved.inject_htmx is True


def test_explicit_keywords_win_over_an_explicit_settings_object():
    """Precedence rule: keywords are the caller's most specific statement, so
    they override both the environment and a passed-in settings object."""
    from pyjinhx2.config import setup

    resolved = setup(settings=PjxSettings(reactive_dev=False), reactive_dev=True)
    assert resolved.reactive_dev is True


def test_components_root_builds_the_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from pyjinhx2 import config

    calls: list[tuple[Path | str, list[type]]] = []
    monkeypatch.setattr(
        config,
        "build_registry",
        lambda template_dir, classes: calls.append((template_dir, list(classes))),
    )
    config.setup(components_root=tmp_path)
    assert len(calls) == 1
    assert calls[0][0] == tmp_path


def test_no_components_root_does_not_build_the_registry(
    monkeypatch: pytest.MonkeyPatch,
):
    from pyjinhx2 import config

    calls: list[object] = []
    monkeypatch.setattr(
        config, "build_registry", lambda template_dir, classes: calls.append(1)
    )
    config.setup()
    assert calls == []


def test_setup_rejects_a_non_asgi_app():
    from pyjinhx2.config import setup

    class NotAnApp:
        pass

    with pytest.raises(TypeError, match="add_middleware"):
        setup(NotAnApp())


def test_setup_delegates_an_asgi_app_to_the_fastapi_integration(
    monkeypatch: pytest.MonkeyPatch,
):
    """#484 owns integrations.fastapi; config only hands the app over to it."""
    integration = types.ModuleType("pyjinhx2.integrations.fastapi")
    integration.apply_setup = MagicMock()  # type: ignore[attr-defined]
    package = types.ModuleType("pyjinhx2.integrations")
    package.fastapi = integration  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyjinhx2.integrations", package)
    monkeypatch.setitem(sys.modules, "pyjinhx2.integrations.fastapi", integration)

    from pyjinhx2.config import setup

    app = MagicMock(spec=["add_middleware", "router"])
    factory = MagicMock()
    resolved = setup(app, context_factory=factory, reactive_dev=True)

    integration.apply_setup.assert_called_once_with(  # type: ignore[attr-defined]
        app, resolved, context_factory=factory
    )
    assert resolved.reactive_dev is True


def test_deferred_cache_machinery_is_not_ported():
    """ADR 0009/0011: no invalidation backend, hub or cache scope in v2."""
    names = {field.name for field in dataclasses.fields(PjxSettings)}
    assert names == {"reactive_dev", "inject_htmx", "components_root", "static_root"}


def test_static_root_is_stored_on_the_settings(tmp_path: Path):
    from pyjinhx2.config import setup

    assert setup(static_root=tmp_path).static_root == tmp_path

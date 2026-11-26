"""Guards that every builtin under `pyjinhx.builtins` opts into extra-attribute passthrough per ADR 0006's strict-core-open-subclass design (#928)."""

import importlib
import inspect
import pkgutil

import pytest
from pydantic import AfterValidator

import pyjinhx.builtins
from pyjinhx.components import discovery
from pyjinhx.components.base import BaseComponent, validate_extra_attrs

# Class names of builtins that legitimately have no root HTML tag to hang
# attributes on. Empty today: every builtin renders a single root element.
EXEMPT_FROM_EXTRA_ATTRS = frozenset()


def discover_builtin_components() -> list[type[BaseComponent]]:
    """Return every BaseComponent subclass defined under `pyjinhx.builtins`."""
    found: dict[str, type[BaseComponent]] = {}
    for module_info in pkgutil.walk_packages(
        pyjinhx.builtins.__path__, prefix="pyjinhx.builtins."
    ):
        module = importlib.import_module(module_info.name)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(cls, BaseComponent)
                and cls is not BaseComponent
                and cls.__module__.startswith("pyjinhx.builtins")
            ):
                found[f"{cls.__module__}.{cls.__qualname__}"] = cls
    return list(found.values())


DISCOVERED = discover_builtin_components()


def _checked_components() -> list[type[BaseComponent]]:
    return [cls for cls in DISCOVERED if cls.__name__ not in EXEMPT_FROM_EXTRA_ATTRS]


def _has_extra_attrs_type(cls: type[BaseComponent]) -> bool:
    field = cls.model_fields.get("extra_attrs")
    if field is None:
        return False
    return field.annotation == dict[str, str] and any(
        isinstance(m, AfterValidator) and m.func is validate_extra_attrs
        for m in field.metadata
    )


def test_every_builtin_declares_extra_attrs():
    offenders = [
        f"{cls.__module__}.{cls.__qualname__}"
        for cls in _checked_components()
        if not _has_extra_attrs_type(cls)
    ]
    assert not offenders, (
        "builtins missing `extra_attrs: ExtraAttrs = Field(default_factory=dict)`: "
        + ", ".join(sorted(offenders))
    )


def test_extra_attrs_default_factory_is_empty_dict():
    offenders = []
    for cls in _checked_components():
        field = cls.model_fields.get("extra_attrs")
        if field is None or field.default_factory is None:
            offenders.append(f"{cls.__module__}.{cls.__qualname__}")
            continue
        if field.default_factory() != {}:  # type: ignore[call-arg]
            offenders.append(f"{cls.__module__}.{cls.__qualname__}")
    assert not offenders, (
        "builtins whose `extra_attrs` does not default to an empty dict: "
        + ", ".join(sorted(offenders))
    )


def test_exemption_list_names_are_still_valid_or_absent():
    by_name = {cls.__name__: cls for cls in DISCOVERED}
    stale = [
        name
        for name in EXEMPT_FROM_EXTRA_ATTRS
        if name in by_name and "extra_attrs" in by_name[name].model_fields
    ]
    assert not stale, (
        "exemptions are no longer needed — these builtins now declare `extra_attrs`: "
        + ", ".join(sorted(stale))
    )


def test_walker_finds_a_nonzero_number_of_builtins():
    assert len(DISCOVERED) >= 50, (
        f"discovery walked only {len(DISCOVERED)} builtin components — "
        "the package walk is likely broken, making the other checks vacuous"
    )


# End-to-end: a user template mounting builtin tags resolves with no manual
# register_class call (issue #738) — setup(components_root=...) alone is enough.


@pytest.fixture(autouse=True)
def reset_registry():
    """discovery._registry is process-global; don't leak a builtins-populated
    mapping into whichever test module runs next in the same process."""
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None
    yield
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None


def test_nested_builtin_tags_expand_after_setup_alone(tmp_path):
    """A user template using <PJXCard><PJXCardBody> renders with no register_class call."""
    import pyjinhx.builtins  # noqa: F401
    from pyjinhx.components.classless import component
    from pyjinhx.config import setup
    from pyjinhx.rendering.pipeline import render
    from pyjinhx.rendering.session import RenderSession

    (tmp_path / "user_page.pjx").write_text(
        "<PJXCard><PJXCardBody>hello</PJXCardBody></PJXCard>"
    )
    setup(app=None, components_root=tmp_path)

    UserPage = component("UserPage")
    html = render(UserPage(), RenderSession())  # pyright: ignore[reportCallIssue]

    assert "hello" in html
    assert 'class="pjx-card' in html  # pjx_card.pjx's actual emitted markup
    assert "PJXCard" not in html

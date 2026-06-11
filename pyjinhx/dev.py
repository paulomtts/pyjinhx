from __future__ import annotations

import logging
from dataclasses import dataclass

from pyjinhx.registry import Registry

from .client import ClientBackend
from .mutations import MutationTracker

logger = logging.getLogger("pyjinhx")


@dataclass
class _DevConfig:
    enabled: bool = False
    strict: bool = False


_dev_config = _DevConfig()


def enable_reactive_dev(*, strict: bool = False) -> None:
    """Enable development-time reactive guardrails (warnings or strict exceptions)."""
    global _dev_config
    _dev_config = _DevConfig(enabled=True, strict=strict)


def disable_reactive_dev() -> None:
    """Disable development-time reactive guardrails."""
    global _dev_config
    _dev_config = _DevConfig()


def _report(message: str) -> None:
    if _dev_config.strict:
        raise RuntimeError(message)
    logger.warning(message)


def warn_mutations_without_render() -> None:
    if not _dev_config.enabled:
        return
    if MutationTracker.pending() and not MutationTracker.render_was_consumed():
        _report(
            "Mutations were recorded via @mutates but no reactive render() "
            "consumed them in this request scope."
        )


def warn_reactive_render_without_client(*, backend: ClientBackend | None) -> None:
    if not _dev_config.enabled or backend is not None:
        return
    if MutationTracker.pending():
        _report(
            "Mutations were recorded but no ClientBackend is active; "
            "out-of-band swaps will be skipped."
        )


def validate_depends_on(instance: object) -> None:
    """Ensure ``depends_on()`` is a subset of the static ``react`` superset."""
    if not _dev_config.enabled:
        return
    component_class = type(instance)
    if not getattr(component_class, "_pjx_reactive", False):
        return
    if not hasattr(instance, "depends_on"):
        return
    superset = set(getattr(component_class, "_pjx_reacts_to", frozenset()))
    runtime = instance.depends_on()
    extra = runtime - superset
    if extra:
        _report(
            f"{component_class.__name__}.depends_on() {extra!r} exceeds "
            f"the static react superset {superset!r}."
        )


def dependency_graph() -> dict[str, list[str]]:
    """
    Map each declared reactive key to component class names that depend on it.

    Shows the static ``react`` superset only — not per-instance narrowing
    from ``depends_on()``.
    """
    graph: dict[str, set[str]] = {}
    for class_name, component_class in Registry.get_classes().items():
        react_keys = getattr(component_class, "_pjx_reacts_to", None)
        if not react_keys:
            continue
        if not getattr(component_class, "_pjx_reactive", False):
            continue
        for key in react_keys:
            graph.setdefault(key, set()).add(class_name)
    return {key: sorted(names) for key, names in sorted(graph.items())}


def format_dependency_graph(*, as_mermaid: bool = False) -> str:
    """Format the dependency graph as a text table or mermaid flowchart."""
    graph = dependency_graph()
    if not graph:
        return "(no reactive components registered)"

    if as_mermaid:
        lines = ["flowchart LR"]
        for key, components in graph.items():
            safe_key = key.replace(":", "_")
            lines.append(f'  key_{safe_key}["{key}"]')
            for component_name in components:
                lines.append(f"  key_{safe_key} --> {component_name}")
        return "\n".join(lines)

    lines = ["Reactive dependency graph:", ""]
    for key, components in graph.items():
        lines.append(f"  {key!r} -> {', '.join(components)}")
    return "\n".join(lines)

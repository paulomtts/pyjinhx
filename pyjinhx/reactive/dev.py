from __future__ import annotations

import logging
from dataclasses import dataclass

from pyjinhx.core.registry import Registry
from .keys import ReactiveKey, interpolate_reactive_keys

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


def warn_reactive_render_without_mounted(
    *,
    dirtied: set[ReactiveKey] | None,
    mounted: object | None,
    own_keys: set[str],
) -> None:
    if not _dev_config.enabled or mounted is not None:
        return
    has_dirtied = dirtied is not None or bool(MutationTracker.pending())
    if has_dirtied or own_keys:
        _report(
            "Reactive dirtied keys are set but mounted was not passed; "
            "out-of-band swaps will be skipped."
        )


def validate_load_reads(
    component_class: type,
    *,
    declared_reads: set[str],
    reacts_to: set[str],
) -> None:
    if not _dev_config.enabled or not declared_reads:
        return
    extra = declared_reads - reacts_to
    if extra:
        _report(
            f"{component_class.__name__}.load_reads {extra!r} is not covered by "
            f"reacts_to {reacts_to!r}."
        )


def validate_depends_on(instance: object) -> None:
    """Ensure ``depends_on()`` is a subset of the static ``reacts_to`` superset."""
    if not _dev_config.enabled:
        return
    component_class = type(instance)
    if not getattr(component_class, "_pjx_reactive", False):
        return
    if not hasattr(instance, "depends_on"):
        return
    superset = interpolate_reactive_keys(
        getattr(component_class, "_pjx_reacts_to", frozenset()),
        getattr(instance, "_pjx_key", None),
        keyed=getattr(component_class, "_pjx_keyed", False),
    )
    runtime = instance.depends_on()
    extra = runtime - superset
    if extra:
        _report(
            f"{component_class.__name__}.depends_on() {extra!r} exceeds "
            f"the static reacts_to superset {superset!r}."
        )


def dependency_graph() -> dict[str, list[str]]:
    """
    Map each declared reactive key to component class names that depend on it.

    Shows the static ``reacts_to`` superset only — not per-instance narrowing
    from ``depends_on()``. Instance-tier stems appear as declared
    (e.g. ``"todo"``), not expanded per key.
    """
    graph: dict[str, set[str]] = {}
    for class_name, component_class in Registry.get_classes().items():
        reacts_to = getattr(component_class, "_pjx_reacts_to", None)
        if not reacts_to:
            continue
        if not getattr(component_class, "_pjx_reactive", False):
            continue
        for key in reacts_to:
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

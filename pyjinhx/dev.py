"""Development-time reactive diagnostics: the declared dependency graph and dev checks.

dev sits above the render spine alongside config and context: it reads
BaseComponent's subclass tree and the request-scoped reactive state, and nothing
below it imports this module back. Every check here is diagnostic — it observes
state that other modules own and never mutates the cache, the dirtied set, or a
render decision.

The checks only run once ``enable_reactive_dev()`` has been called, which
``config.configure_pyjinhx`` does for ``PjxSettings.reactive_dev``. Disabled is
the default and a plain no-op.
"""

import logging
from dataclasses import dataclass

from pyjinhx.component import BaseComponent
from pyjinhx.session import get_cache_reverse, get_dirtied

logger = logging.getLogger("pyjinhx")


@dataclass(frozen=True)
class _DevConfig:
    """Whether the dev checks run, and whether a finding raises."""

    enabled: bool = False
    strict: bool = False


_dev_config = _DevConfig()


def enable_reactive_dev(*, strict: bool = False) -> None:
    """Turn the development-time reactive checks on.

    Args:
        strict: When True a finding raises RuntimeError instead of logging a
            warning.
    """
    global _dev_config
    _dev_config = _DevConfig(enabled=True, strict=strict)


def disable_reactive_dev() -> None:
    """Turn the development-time reactive checks off."""
    global _dev_config
    _dev_config = _DevConfig()


def _report(message: str) -> None:
    """Raise or log ``message``, depending on the configured strictness."""
    if _dev_config.strict:
        raise RuntimeError(message)
    logger.warning(message)


def _all_component_classes() -> list[type]:
    """Every declared BaseComponent subclass, nested ones included."""
    found: list[type] = []
    stack = list(BaseComponent.__subclasses__())
    while stack:
        cls = stack.pop()
        found.append(cls)
        stack.extend(cls.__subclasses__())
    return found


def dependency_graph() -> dict[str, list[str]]:
    """Map each declared reactive key to the class names that depend on it.

    Reads the static ``react=(...)`` declarations recorded on each class, never
    per-request state, so the answer is the same inside and outside a request.

    Returns:
        Reactive key -> sorted class names, itself sorted by key.
    """
    graph: dict[str, set[str]] = {}
    for cls in _all_component_classes():
        # getattr rather than an isinstance check on ReactiveComponent: a plain
        # BaseComponent subclass simply has no such attribute, and reading it
        # this way keeps dev off reactive/'s import list.
        # Pydantic represents an unset private attr as a ModelPrivateAttr
        # placeholder on the class object itself (e.g. ReactiveComponent, the
        # abstract base, never runs the __init_subclass__ hook that resolves
        # it to a real tuple); only a genuine tuple is a declared dependency.
        react_keys = getattr(cls, "_pjx_react_keys", ())
        if not isinstance(react_keys, tuple):
            continue
        for key in react_keys:
            graph.setdefault(key, set()).add(cls.__name__)
    return {key: sorted(names) for key, names in sorted(graph.items())}


def format_dependency_graph(*, as_mermaid: bool = False) -> str:
    """Render the dependency graph for a human or for mermaid.

    Args:
        as_mermaid: When True, emit a ``flowchart LR`` graph with one edge per
            key -> component pair. Otherwise emit an indented text listing.

    Returns:
        The rendered graph; a placeholder line when no class declares a key.
    """
    graph = dependency_graph()
    if as_mermaid:
        lines = ["flowchart LR"]
        for key, names in graph.items():
            # ':' separates a reactive key's namespace from its id but is not
            # legal in a mermaid node id, so the id is sanitized and the label
            # carries the real key.
            node = f"key_{key.replace(':', '_')}"
            lines.append(f'  {node}["{key}"]')
            for name in names:
                lines.append(f"  {node} --> {name}")
        return "\n".join(lines)
    if not graph:
        return "(no reactive components registered)"
    lines = ["Reactive dependency graph:", ""]
    for key, names in graph.items():
        lines.append(f"  {key!r} -> {', '.join(names)}")
    return "\n".join(lines)


def warn_unconsumed_mutations() -> None:
    """Report dirtied reactive keys that nothing in this request depends on.

    A key is unconsumed when the load cache's reverse index holds no entry
    under it: no ``load()`` in this request declared a dependency on that key,
    so dirtying it evicts nothing. That usually means a typo in the key, a key
    nothing reads any more, or a ``dirty()`` that fired before the load which
    would have registered the dependency.

    Observational only: it reads the reverse index other modules populate and
    never evicts, dirties or re-renders anything. A no-op when dev mode is off
    or nothing was dirtied.
    """
    if not _dev_config.enabled:
        return
    reverse = get_cache_reverse()
    # An empty membership set is as unconsumed as a missing key: invalidate()
    # prunes sets in place rather than deleting them.
    unconsumed = sorted(key for key in get_dirtied() if not reverse.get(key))
    if not unconsumed:
        return
    _report(
        f"Reactive keys {unconsumed} were dirtied but nothing in this request "
        f"loaded under them, so dirtying them evicted nothing."
    )

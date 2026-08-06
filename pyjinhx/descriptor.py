"""The per-class fact sheet: what a component class resolved to, frozen once.

Import-pure — stdlib only. Nothing in pyjinhx may be imported here.
descriptor.py sits above _component.py and below rendering.py in the import graph.
This module defines the data shape only; resolution of values happens elsewhere.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ClassDescriptor:
    """Per-class resolution results, immutable after creation.

    Holds the single template probe result, asset paths (resolved per-kind up
    the MRO), slot fields, the children target, strict mode flag, and
    provenance mapping (kind → ancestor class).
    """

    template_path: Path
    slot_fields: frozenset[str]
    children_field: str | None
    css_paths: tuple[Path, ...]
    js_paths: tuple[Path, ...]
    strict: bool
    provenance: Mapping[str, type]
    has_stale_def_header: bool = False
    """Whether the resolved template still carries a ``{#def#}`` header this
    class-based component ignores. Answered once, when ``template_path`` is
    resolved, so no render pays for the probe."""
    json_coercible_fields: frozenset[str] = frozenset()
    """Declared fields whose annotation makes them JSON-coercion candidates —
    see :func:`pyjinhx._component._is_json_coercible_annotation`. Resolved
    once per class at registration, mirroring ``slot_fields``."""

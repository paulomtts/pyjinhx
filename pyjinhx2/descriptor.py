"""The per-class fact sheet: what a component class resolved to, frozen once.

Import-pure — stdlib only. Nothing in pyjinhx2 may be imported here.
descriptor.py sits above component.py and below render.py in the import graph,
and holds that boundary the same way segments.py does.

This module is the data shape only. Resolving the values — the single template
probe (ADR 0007), the per-kind MRO walk and provenance (ADR 0010), slot-field
detection, co-located asset discovery — lands in the sibling issues #271-#278
and never runs at import time here.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ClassDescriptor:
    """Everything a component class derives once, at registration (invariant 5).

    Computed in ``__pydantic_init_subclass__`` (#271) and never mutated after:
    a dev-reload rebuild (#278) replaces the whole object rather than editing a
    field, which is what ``frozen=True`` is here to enforce.

    ``template_path`` is a single path, not a list — one class, one probe, one
    convention (ADR 0007). ``css_paths`` and ``js_paths`` stay separate fields
    rather than one collapsed ``asset_paths`` because each kind resolves
    independently up the MRO (ADR 0010); merging them would force them back into
    lockstep. ``strict`` records the ADR 0006 mode once per class so render.py
    branches on it per class instead of per render.

    ``provenance`` maps a kind name (``"template"``, ``"css"``, ``"js"``) to the
    ancestor class that supplied it. Keyed by string rather than fixed fields so
    #274 can record kinds this issue did not have to predict. Typed ``Mapping``
    to signal "never mutated after creation" even though a frozen dataclass
    cannot enforce that on the value itself.

    Not hashable in practice: the generated ``__hash__`` exists but raises on a
    dict-valued ``provenance``. Nothing downstream keys a cache by descriptor,
    so this is left as-is rather than papered over with MappingProxyType —
    equality and identity are the only comparisons anything needs.

    No validation lives here. Constructing a descriptor with a template path
    that does not exist is the resolvers' problem to never do (#272-#274); this
    class accepts exactly what ``@dataclass`` generates.
    """

    template_path: Path
    slot_fields: frozenset[str]
    css_paths: tuple[Path, ...]
    js_paths: tuple[Path, ...]
    strict: bool
    provenance: Mapping[str, type]

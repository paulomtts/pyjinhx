"""Whether a ReactiveComponent's load() costs enough to be worth a fan-out thread."""

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyjinhx.reactive.component import ReactiveComponent

# Handing one candidate to the threadpool is not free: the submit, the
# copy_context() copy the worker runs under and the join come to roughly 50-100us
# per item, which is why the bench's zero-cost load() row loses at 0.3-0.4x. The
# floor sits clear above a load() that only touches memory and well below the
# 0.5ms row that already wins 2.8x, so nothing that profits is demoted.
_DEFAULT_MIN_COST_US = 200.0

# Qualified names, not classes: see _too_cheap_key. Process-wide because the
# measurement is a property of the load implementation, not of any one request.
_too_cheap: set[str] = set()
_decided: set[str] = set()


def reset_load_cost_decisions() -> None:
    """Forget every measured class. For tests, which must not inherit a verdict."""
    _too_cheap.clear()
    _decided.clear()


def _min_cost_us() -> float:
    """The load() cost, in microseconds, below which threading the build is a loss.

    Read per call rather than captured at import so a test — or an app that sets
    the variable after importing pyjinhx — is not fighting import order.
    """
    raw = os.environ.get("PJX_FANOUT_THREAD_MIN_US")
    if raw is None or raw == "":
        return _DEFAULT_MIN_COST_US
    try:
        return float(raw)
    except ValueError:
        raise ValueError(
            f"PJX_FANOUT_THREAD_MIN_US={raw!r} is not a number of microseconds."
        ) from None


def is_too_cheap_to_thread(cls: "type[ReactiveComponent]") -> bool:
    """Whether this class's load() was measured as cheaper than a thread costs.

    False for a class nobody has measured yet: fan-out threads by default and a
    class earns its way out, so the first build of an unseen class behaves the
    same as it did before any of this existed.
    """
    return _too_cheap_key(cls) in _too_cheap


def note_load_cost(cls: "type[ReactiveComponent]", cost_us: float) -> None:
    """Record what this class's load() actually cost, and decide it once.

    Per class rather than per instance: the same load() doing the same work costs
    the same whether it is row 3 or row 197, so one measurement settles every
    instance and the check afterwards is a set lookup.

    Decided once and never revisited. A class that re-measured could flip between
    requests on nothing but machine load, and a build pass that threads or does
    not thread according to scheduling noise is one nobody can reason about.
    """
    key = _too_cheap_key(cls)
    if key in _decided:
        return
    _decided.add(key)
    if cost_us < _min_cost_us():
        _too_cheap.add(key)


def _too_cheap_key(cls: "type[ReactiveComponent]") -> str:
    """The qualified name this class is remembered under.

    A name rather than the class object, so the two sets cannot keep a class alive
    for the life of the process.
    """
    return f"{cls.__module__}.{cls.__qualname__}"

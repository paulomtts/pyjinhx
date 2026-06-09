"""
Reactive subsystem for pyjinhx.

Modules:
- ``reactive`` — ``ReactiveComponent``, render dispatch, ``oob_swaps``, and the ``PjxLoad`` field marker
- ``cache`` — ``LoadCache`` memoization for ``load()`` and cross-process invalidation
- ``mutations`` — ``MutationTracker``, ``@mutates``
- ``client`` — ``ClientBackend``, mounted/trigger/asset manifest parsing, and ``client_script`` runtime injection
- ``keys`` — reactive key coercion and ``StateKey``
- ``context`` — ``LoadContext`` for ``load()`` DI
- ``dev`` — development guardrails and dependency graph
"""

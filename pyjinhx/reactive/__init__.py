"""
Reactive subsystem for pyjinhx.

Modules:
- ``component`` — ``ReactiveComponent``, ``depends_on()``, render descriptor
- ``render`` — shared reactive render orchestration
- ``load_cache`` — ``LoadCache`` memoization for ``load()``
- ``mutations`` — ``MutationTracker``, ``@mutates``
- ``pjx_load`` — ``PjxLoad`` field marker for ``data-pjx-load`` stamping
- ``invalidation`` — ``InvalidationBackend`` ABC and ``InvalidationHub``
- ``client`` — ``ClientBackend``, mounted/trigger/asset manifest parsing, and ``client_script`` runtime injection
- ``oob`` — out-of-band HTMX swap computation
- ``keys`` — reactive key coercion and ``StateKey``
- ``context`` — ``LoadContext`` for ``load()`` DI
- ``dev`` — development guardrails and dependency graph
"""

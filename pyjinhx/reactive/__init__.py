"""
Reactive subsystem for pyjinhx.

Modules:
- ``component`` — ``ReactiveComponent``, ``effective_reacts_to()``, render descriptor
- ``render`` — shared reactive render orchestration
- ``load_cache`` — ``LoadCache`` memoization for ``load()``
- ``mutations`` — ``MutationTracker``, ``@mutates``, ``mutation_scope``
- ``invalidation`` — ``InvalidationBackend`` ABC and ``InvalidationHub``
- ``payload`` — client header parsing (``MountedManifest``, ``LoadedAssets``)
- ``oob`` — out-of-band HTMX swap computation
- ``runtime`` — ``client_script`` injection
- ``keys`` — reactive key coercion and ``StateKey``
- ``context`` — ``LoadContext`` for ``load()`` DI
- ``backend`` — ``ClientBackend`` ABC for request headers
- ``dev`` — development guardrails and dependency graph
"""

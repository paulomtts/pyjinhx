"""
Core subsystem for pyjinhx.

Modules:
- ``base`` — ``BaseComponent`` and nesting wrappers
- ``renderer`` — ``Renderer`` orchestration
- ``renderer_settings`` — process-wide renderer defaults and factory cache
- ``template_load`` — Jinja template discovery and loading
- ``render_context`` — registry context injection and reactive stamping
- ``render_assets`` — asset collection and injection helpers
- ``tag_expand`` — PascalCase tag parsing and rendering
- ``autodiscover`` — co-located component module import
- ``registry`` — class and request-scoped instance registry
- ``finder`` — template and asset file discovery
- ``parser`` — HTML-like tag parser
- ``assets`` — ``RenderSession``, ``AssetMode``, manifest helpers
- ``tag`` — parsed tag node type
"""

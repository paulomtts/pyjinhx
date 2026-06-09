"""
Core subsystem for pyjinhx.

Modules:
- ``base`` — ``BaseComponent`` and nesting wrappers
- ``renderer`` — ``Renderer`` orchestration
- ``renderer_settings`` — process-wide renderer defaults and factory cache
- ``template_load`` — Jinja template discovery and loading
- ``render_context`` — registry context injection and reactive stamping
- ``tags`` — PascalCase tag node, HTML parser, expansion, and autodiscovery
- ``registry`` — class and request-scoped instance registry
- ``finder`` — template and asset file discovery
- ``assets`` — ``RenderSession``, ``AssetMode``, manifest helpers, asset collection and injection
"""

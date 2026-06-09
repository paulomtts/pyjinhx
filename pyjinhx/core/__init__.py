"""
Core subsystem for pyjinhx.

Modules:
- ``base`` — ``BaseComponent`` and nesting wrappers
- ``renderer`` — ``Renderer`` orchestration, process-wide defaults, template resolution, render context, reactive stamping
- ``tags`` — PascalCase tag node, HTML parser, expansion, and autodiscovery
- ``registry`` — class and request-scoped instance registry
- ``finder`` — template and asset file discovery
- ``assets`` — ``RenderSession``, ``AssetMode``, manifest helpers, asset collection and injection
"""

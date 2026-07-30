"""L0.4.4 render — single-level pipeline.

Descriptor read → context build → Jinja render → single parse → RenderedLevel.
"""

from typing import TYPE_CHECKING
from pyjinhx2.component import BaseComponent
from pyjinhx2.segments import RenderedLevel, VerbatimParser

if TYPE_CHECKING:
    from pyjinhx2.session import RenderSession


def render(component: BaseComponent, session: "RenderSession") -> RenderedLevel:
    """Render one component level: template → one parse → RenderedLevel.

    Args:
        component: A valid BaseComponent instance (construction-time validation passed).
        session: RenderSession providing Jinja environment and hooks.

    Returns:
        RenderedLevel with segments (str | ChildRef), root_span, descriptor.

    Raises:
        ValueError: If template renders zero or 2+ root elements.
        jinja2.TemplateNotFound: If template file missing.
        jinja2.TemplateAssertionError: If Jinja evaluation fails.
    """
    # Phase 1: Descriptor read
    descriptor = component.__class__.__pjx_descriptor__

    # Phase 2: Context build
    context = {}
    for field_name in component.__class__.model_fields:
        field_value = getattr(component, field_name)
        context[field_name] = field_value

    # Phase 3: Jinja render with autoescape ON
    jinja_env = session.jinja_env
    template = jinja_env.get_template(str(descriptor.template_path))
    output_string = template.render(context)

    # Phase 4: Single parse via VerbatimParser
    parser = VerbatimParser()
    parser.feed(output_string)
    parser.close()

    # Validate single-root rule
    parser.enforce_single_root()

    # Return RenderedLevel
    return RenderedLevel(
        segments=parser.segments,
        root_span=parser.root_span or (0, 0),
        descriptor=descriptor
    )

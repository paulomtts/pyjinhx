"""L0.4.4/L0.4.6 render — single-level pipeline and public API.

Descriptor read → context build → Jinja render → single parse → RenderedLevel
(render_level, internal). serialize(render_level(...)) closes the loop into a
finished HTML string for a childless component (render, public API).
"""

import jinja2

from pyjinhx2.component import BaseComponent
from pyjinhx2.segments import RenderedLevel, VerbatimParser, serialize
from pyjinhx2.session import RenderSession


def render_level(component: BaseComponent, session: "RenderSession") -> RenderedLevel:
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
    prefix = f"{component.__class__.__name__} (template: {descriptor.template_path}): "
    try:
        template = jinja_env.get_template(str(descriptor.template_path))
    except jinja2.TemplateNotFound as err:
        raise jinja2.TemplateNotFound(
            err.name, message=f"{prefix}template file not found"
        ) from err
    output_string = template.render(context)

    # Phase 4: Single parse via VerbatimParser
    parser = VerbatimParser()
    parser.feed(output_string)
    parser.close()

    # Validate single-root rule
    try:
        parser.enforce_single_root()
    except ValueError as err:
        raise ValueError(f"{prefix}{err}") from err

    # Return RenderedLevel
    return RenderedLevel(
        segments=parser.segments,
        root_span=parser.root_span or (0, 0),
        descriptor=descriptor,
    )


def render(component: BaseComponent, session: "RenderSession | None" = None) -> str:
    """Render a component to a final HTML string (public API).

    Thin wrapper closing the loop for a childless component: render_level()
    produces one component's RenderedLevel, serialize() joins its segments
    back into markup. Internal/recursive callers (L1) call render_level()
    directly instead, since they need the RenderedLevel, not a string.

    Args:
        component: A valid BaseComponent instance.
        session: RenderSession providing the Jinja environment. Defaults to
            a fresh RenderSession() when omitted, so callers outside the
            kernel don't need to construct one by hand.

    Returns:
        The component's rendered markup as a finished HTML string.

    Raises:
        ValueError: If template renders zero or 2+ root elements.
        jinja2.TemplateNotFound: If template file missing.
        jinja2.TemplateAssertionError: If Jinja evaluation fails.
        AssertionError: If a segment reaching serialize() is neither str
            nor RenderedLevel (unresolved ChildRef reaching the boundary).
    """
    if session is None:
        session = RenderSession()
    level = render_level(component, session)
    return serialize(level)

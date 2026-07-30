"""L0.4.4 render — single-level pipeline.

Descriptor read → context build → Jinja render → single parse → RenderedLevel.
"""

from typing import TYPE_CHECKING
from pyjinhx2.component import BaseComponent
from pyjinhx2.segments import RenderedLevel

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

    # Placeholder for phases 2-4
    raise NotImplementedError("render pipeline not yet complete")

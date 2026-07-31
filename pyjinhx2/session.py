"""RenderSession — provides Jinja environment and render hooks."""

from jinja2 import Environment, FileSystemLoader

from pyjinhx2.markers import finalize_slot_node


class RenderSession:
    """Session providing Jinja environment with autoescape enabled."""

    def __init__(self, template_dir: str = "templates"):
        """Initialize render session.

        Args:
            template_dir: Directory to load templates from (default: "templates").
        """
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True,
            # Interpolating a component-valued slot must not stringify it; the
            # hook swaps in a placeholder the render pipeline resolves later.
            finalize=finalize_slot_node,
        )

import pytest
from pathlib import Path
from pyjinhx2.session import RenderSession


@pytest.fixture
def render_session():
    """Provide a RenderSession configured to load templates from tests/templates."""
    template_dir = Path(__file__).parent.parent / "templates"
    return RenderSession(template_dir=str(template_dir))

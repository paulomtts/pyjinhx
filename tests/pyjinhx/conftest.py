import pytest

from pyjinhx.session import RenderSession


@pytest.fixture
def render_session():
    """Provide a RenderSession for tests."""
    return RenderSession()

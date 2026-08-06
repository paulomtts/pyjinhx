import pytest

from pyjinhx.reactive.load_cost import reset_load_cost_decisions
from pyjinhx.render_cache import reset_render_cost_decisions
from pyjinhx.session import RenderSession


@pytest.fixture
def render_session():
    """Provide a RenderSession for tests."""
    return RenderSession()


@pytest.fixture(autouse=True)
def render_cost_decisions():
    """Clear the per-class render-cost verdicts around every test.

    They are process-wide and decided once, so without this the first test to
    render a class would fix whether the render cache applies to it for the rest
    of the session — and which test ran first would decide it.
    """
    reset_render_cost_decisions()
    yield
    reset_render_cost_decisions()


@pytest.fixture(autouse=True)
def load_cost_decisions():
    """Clear the per-class load-cost verdicts around every test.

    Same rationale as render_cost_decisions: process-wide, decided once, so
    without this the first test to build a class through fan-out would fix its
    threading verdict for the rest of the session.
    """
    reset_load_cost_decisions()
    yield
    reset_load_cost_decisions()


@pytest.fixture(autouse=True)
def cache_everything_by_default(monkeypatch: pytest.MonkeyPatch):
    """Disarm the too-cheap heuristic for tests that are not about it.

    The templates here are a few tags long and render in single-digit
    microseconds, so in production the heuristic would rightly decline every one
    of them. Tests covering the cache *mechanism* still need it to engage, so the
    floor drops to zero unless a test sets its own.
    """
    monkeypatch.setenv("PJX_RENDER_CACHE_MIN_US", "0")

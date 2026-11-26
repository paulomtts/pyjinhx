import importlib
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from pyjinhx.components import discovery
from pyjinhx.reactive.load_cost import reset_load_cost_decisions
from pyjinhx.rendering.render_cache import reset_render_cost_decisions
from pyjinhx.rendering.session import RenderSession

Write = Callable[[str, str], Path]

TESTS = Path(__file__).parent


def pytest_collection_modifyitems(items):
    for item in items:
        if not item.path.is_relative_to(TESTS):
            continue
        folder = item.path.relative_to(TESTS).parts[0]
        if folder in ("browser", "docs"):
            item.add_marker(folder)


@pytest.fixture
def render_session():
    """Provide a RenderSession for tests."""
    return RenderSession()


@pytest.fixture
def session():
    """A plain RenderSession, for the tests that do not define their own."""
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
def no_orphan_templates():
    """Start every test with no orphan templates published.

    Most registry fixtures reset only the mapping and template_dir, so an
    orphan recorded by an earlier test's build would otherwise outlive the tree
    it was walked from and answer a tag in an unrelated test.
    """
    discovery._registry.orphans = {}
    yield
    discovery._registry.orphans = {}


@pytest.fixture(autouse=True)
def cache_everything_by_default(monkeypatch: pytest.MonkeyPatch):
    """Disarm the too-cheap heuristic for tests that are not about it.

    The templates here are a few tags long and render in single-digit
    microseconds, so in production the heuristic would rightly decline every one
    of them. Tests covering the cache *mechanism* still need it to engage, so the
    floor drops to zero unless a test sets its own.
    """
    monkeypatch.setenv("PJX_RENDER_CACHE_MIN_US", "0")


@pytest.fixture
def write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Write files under ``tmp_path``, which is on ``sys.path``; modules the
    test imported from there are forgotten afterwards."""
    monkeypatch.syspath_prepend(str(tmp_path))
    before = set(sys.modules)

    def write_file(name: str, text: str) -> Path:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        importlib.invalidate_caches()
        return path

    write_file("pkg/__init__.py", "")
    yield write_file
    for name in set(sys.modules) - before:
        del sys.modules[name]

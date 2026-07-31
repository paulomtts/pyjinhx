"""L2.4.1: a FastAPI-threadpool-shaped harness over the real render pipeline.

FastAPI dispatches sync path-operation functions onto a ThreadPoolExecutor, so
a pyjinhx request runs on a borrowed worker thread with sibling requests running
beside it. These tests reproduce that shape: N threads, each in its own
request_scope(), each driving render() against shared component classes, shared
descriptors, a shared Jinja template cache and shared asset files on disk.

What is proven here is the ContextVar half of invariant 4 - that per-request
state never crosses threads - and that concurrent real file reads (template
loads, emit_assets' INLINE reads) never produce FileNotFoundError-class races.
The census enumeration itself belongs to #437, which plugs its assertion into
this harness through run_concurrent_requests' `inspect` hook.
"""

import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pytest

from pyjinhx2 import discovery
from pyjinhx2.component import BaseComponent
from pyjinhx2.descriptor import ClassDescriptor
from pyjinhx2.registry import register_rendered_instance
from pyjinhx2.render import render
from pyjinhx2.session import (
    RenderSession,
    accumulate_assets,
    current_session,
    get_cache_store,
    get_dirtied,
    get_instances,
    request_scope,
)

# 8 matches the v0.x test_thread_safety.py precedent: enough threads that a
# non-isolated store is hit reliably, few enough that the barrier timeouts below
# stay generous on a loaded CI box.
WORKERS = 8

TEMPLATE_DIR = str(Path(__file__).parent.parent / "templates")

# Barrier waits carry a timeout so a genuine deadlock fails the suite instead of
# hanging it; the value is a liveness backstop, not a performance assertion.
BARRIER_TIMEOUT = 15.0


class _ConcAlpha(BaseComponent):
    """Shared across half the workers, so its descriptor is read concurrently."""

    title: str = ""


class _ConcBeta(BaseComponent):
    """The other half's class. Distinct assets make cross-thread bleed visible."""

    title: str = ""


@dataclass(frozen=True)
class Observation:
    """One worker's snapshot of its own request-scoped state.

    Attributes:
        index: The worker's index, 0-based.
        thread_name: The thread the worker actually ran on.
        html: What render() returned, assets included.
        released_at: perf_counter() reading taken the moment the start barrier
            released this worker, used by the barrier sanity check.
        css_assets: The session's accumulated CSS paths at snapshot time.
        js_assets: The session's accumulated JS paths at snapshot time.
        instance_keys: This request's instance registry keys at snapshot time.
        dirtied: This request's dirtied keys at snapshot time.
    """

    index: int
    thread_name: str
    html: str
    released_at: float
    css_assets: frozenset[Path]
    js_assets: frozenset[Path]
    instance_keys: frozenset[str]
    dirtied: frozenset[str]


@pytest.fixture(scope="session", autouse=True)
def concurrency_assets(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Write the real CSS/JS files these components declare and bind descriptors.

    The files are real because emit_assets under INLINE mode read_text()s them on
    every render - that read is one of the two race surfaces under test, so it
    must not be stubbed out. Descriptors are built by hand and assigned, the same
    way test_render_level.py and test_session.py do, since template and asset
    resolution is an MRO/filesystem walk with no override attribute.
    """
    assets = tmp_path_factory.mktemp("concurrency_assets")
    alpha_css = assets / "alpha.css"
    alpha_css.write_text(".alpha { color: red; }")
    alpha_js = assets / "alpha.js"
    alpha_js.write_text("console.log('alpha');")
    beta_css = assets / "beta.css"
    beta_css.write_text(".beta { color: blue; }")
    beta_js = assets / "beta.js"
    beta_js.write_text("console.log('beta');")

    _ConcAlpha.__pjx_descriptor__ = ClassDescriptor(
        template_path=Path("div.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(alpha_css,),
        js_paths=(alpha_js,),
        strict=True,
        provenance={"template": _ConcAlpha},
    )
    _ConcBeta.__pjx_descriptor__ = ClassDescriptor(
        template_path=Path("div.html"),
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(beta_css,),
        js_paths=(beta_js,),
        strict=True,
        provenance={"template": _ConcBeta},
    )
    return assets


def _component_for(index: int) -> BaseComponent:
    """The component worker `index` renders: alternating class, per-worker id.

    Alternating rather than one class each so several threads share one
    descriptor and one template-cache entry (real contention), while the two
    asset sets still differ - a worker seeing the other class's CSS is bleed.
    """
    cls = _ConcAlpha if index % 2 == 0 else _ConcBeta
    return cls(id=f"w{index}", title=f"worker-{index}")


def render_shared_components(index: int, session: RenderSession) -> str:
    """Default harness job: render this worker's component through render()."""
    return render(_component_for(index), session)


def cache_marker_for(index: int) -> str:
    """The key worker `index` stamps into its own LoadCache request store."""
    return f"cache-{index}"


def census_job(index: int, session: RenderSession) -> str:
    """Render as usual, but first stamp this worker's LoadCache store.

    Nothing in the render path writes to the cache store yet (LoadCache lands
    later), so the store would otherwise be empty in every worker and an
    isolation assertion over it would hold vacuously. Writing the marker inside
    the job puts it in before the mid barrier, so by the time the probe runs
    every worker has written - which is the only arrangement where one worker
    seeing a sibling's marker is actually observable.
    """
    get_cache_store()[cache_marker_for(index)] = index
    return render_shared_components(index, session)


def expected_for(
    index: int,
) -> tuple[frozenset[Path], frozenset[Path], frozenset[str], frozenset[str]]:
    """Exactly what worker `index` must observe - no more, no less."""
    cls = _ConcAlpha if index % 2 == 0 else _ConcBeta
    descriptor = cls.__pjx_descriptor__
    return (
        frozenset(descriptor.css_paths),
        frozenset(descriptor.js_paths),
        frozenset({f"{cls.__name__}_w{index}"}),
        frozenset({f"dirty-{index}"}),
    )


def fail_on_errors(errors: list[BaseException]) -> None:
    """Fail the test with every worker exception spelled out, never silently."""
    if errors:
        pytest.fail(
            "worker threads raised:\n"
            + "\n".join(f"  {type(e).__name__}: {e}" for e in errors)
        )


def run_concurrent_requests(
    job: Callable[[int, RenderSession], str],
    *,
    workers: int = WORKERS,
    template_dir: str = TEMPLATE_DIR,
    inspect: Callable[[int, RenderSession, Observation], None] | None = None,
) -> tuple[dict[int, Observation], list[BaseException]]:
    """Run `job` in `workers` threads, each in its own request_scope().

    Shaped like FastAPI's sync dispatch: a ThreadPoolExecutor, one request per
    worker thread. Two barriers do the work. The first releases every worker at
    once so the renders genuinely overlap. The second holds every worker after
    its render but *before* its snapshot, so all N requests' ContextVar state is
    alive simultaneously - which is the only arrangement in which cross-thread
    bleed is observable at all.

    Args:
        job: Called as job(index, session) inside the worker's live scope;
            returns the rendered HTML.
        workers: How many threads/requests to run.
        template_dir: Template directory the per-worker RenderSession loads from.
        inspect: Optional callback run inside the still-open scope, after the
            snapshot is taken. This is the extension point for #437's
            invariant-4 census assertion; anything it raises is collected into
            the returned errors list like any other worker failure.

    Returns:
        A (observations by worker index, collected exceptions) pair. Callers
        pass the second to fail_on_errors() before asserting on the first.
    """
    start = threading.Barrier(workers)
    mid = threading.Barrier(workers)
    observations: dict[int, Observation] = {}
    errors: list[BaseException] = []

    def worker(index: int) -> None:
        try:
            with request_scope(template_dir=template_dir) as session:
                # request_scope subscribes nothing by itself; a request that
                # wants assets accumulated and instances registered wires its
                # own hooks, exactly as an app's request middleware would.
                session.on_rendered.append(accumulate_assets)
                session.on_rendered.append(register_rendered_instance)
                start.wait(timeout=BARRIER_TIMEOUT)
                released_at = time.perf_counter()
                html = job(index, session)
                get_dirtied().add(f"dirty-{index}")
                mid.wait(timeout=BARRIER_TIMEOUT)
                observation = Observation(
                    index=index,
                    thread_name=threading.current_thread().name,
                    html=html,
                    released_at=released_at,
                    css_assets=frozenset(session.css_assets),
                    js_assets=frozenset(session.js_assets),
                    instance_keys=frozenset(get_instances()),
                    dirtied=frozenset(get_dirtied()),
                )
                if inspect is not None:
                    inspect(index, session, observation)
                observations[index] = observation
        except BaseException as exc:  # noqa: BLE001 - surfaced on the main thread
            errors.append(exc)
            # A worker that died before a barrier would strand its siblings
            # there for the full timeout; break both so the failure is reported
            # in seconds and the real exception is the first one in the list.
            start.abort()
            mid.abort()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(worker, range(workers)))
    return observations, errors


def assert_no_bleed(
    observations: dict[int, Observation], workers: int = WORKERS
) -> None:
    """Assert every worker saw its own state and nothing any sibling produced."""
    assert set(observations) == set(range(workers)), (
        f"missing observations from workers {sorted(set(range(workers)) - set(observations))}"
    )
    for index, observed in sorted(observations.items()):
        css, js, keys, dirtied = expected_for(index)
        for label, actual, wanted in (
            ("css_assets", observed.css_assets, css),
            ("js_assets", observed.js_assets, js),
            ("instance_keys", observed.instance_keys, keys),
            ("dirtied", observed.dirtied, dirtied),
        ):
            assert actual == wanted, (
                f"worker {index} ({observed.thread_name}) {label} bled: "
                f"leaked-in={sorted(str(x) for x in actual - wanted)} "
                f"missing={sorted(str(x) for x in wanted - actual)}"
            )


def test_concurrent_renders_no_state_bleed():
    """Each request's assets, registry and dirtied set stay its own."""
    observations, errors = run_concurrent_requests(render_shared_components)

    fail_on_errors(errors)
    assert_no_bleed(observations)
    for index, observed in observations.items():
        assert f"worker-{index}" in observed.html


def _slow(original, delay: float):
    """Wrap `original` so it yields the GIL mid-call, widening the race window."""

    def wrapper(*args, **kwargs):
        time.sleep(delay)
        return original(*args, **kwargs)

    return wrapper


def test_concurrent_renders_no_filenotfound_races(monkeypatch):
    """Slowed-down real disk I/O must not turn into missing-file failures.

    Both file-touching surfaces are widened: the Jinja FileSystemLoader's
    get_source (template loads) and emit_assets' INLINE reads via
    pyjinhx2.assets._inline_tags. Without this the test could pass simply
    because each render finishes before the next thread starts - the same
    reason the v0.x Finder thread-safety test monkeypatches a slow os.walk.
    """
    from jinja2 import FileSystemLoader

    import pyjinhx2.assets as assets_module

    monkeypatch.setattr(
        FileSystemLoader, "get_source", _slow(FileSystemLoader.get_source, 0.02)
    )
    monkeypatch.setattr(
        assets_module, "_inline_tags", _slow(assets_module._inline_tags, 0.02)
    )

    observations, errors = run_concurrent_requests(render_shared_components)

    missing = [e for e in errors if isinstance(e, FileNotFoundError | OSError)]
    assert not missing, (
        "concurrent file reads raised missing-file errors:\n"
        + "\n".join(f"  {type(e).__name__}: {e}" for e in missing)
    )
    fail_on_errors(errors)
    assert_no_bleed(observations)
    for observed in observations.values():
        assert "<style>" in observed.html
        assert "<script>" in observed.html


def test_harness_barrier_actually_synchronizes():
    """The start barrier must release all workers together, or the other two
    tests prove nothing: serialised 'concurrent' renders never contend."""
    observations, errors = run_concurrent_requests(render_shared_components)

    fail_on_errors(errors)
    release_times = [o.released_at for o in observations.values()]
    spread = max(release_times) - min(release_times)
    assert spread < 1.0, (
        f"workers were released {spread:.3f}s apart; the barrier is not "
        "synchronising them, so the renders may never have overlapped"
    )
    thread_names = {o.thread_name for o in observations.values()}
    assert len(thread_names) == WORKERS, (
        f"expected {WORKERS} distinct worker threads, saw {sorted(thread_names)}"
    )


def test_invariant_4_census():
    """Every member of the invariant-4 census, asserted under real concurrency.

    Invariant 4 (architecture-overview.md:107, :168) names exactly what mutable
    state pyjinhx has: a class registry + descriptors built once and swapped in
    at import/registration time, and four ContextVar-held per-request stores -
    instance registry, RenderSession, dirtied keys, LoadCache request store.
    The two halves get opposite assertions. The four request stores must differ
    per worker; the registry and descriptors must be the *same objects* in every
    worker, since a per-thread copy would mean the build-then-swap discipline
    had quietly become per-request rebuilding.
    """
    shared_sightings: dict[int, tuple[int, int, int]] = {}
    sessions_seen: dict[int, int] = {}

    def census_probe(index: int, session: RenderSession, observed: Observation) -> None:
        _, _, expected_keys, expected_dirtied = expected_for(index)

        # 1. Instance registry: this worker's keys, nothing a sibling made.
        assert set(get_instances()) == set(expected_keys), (
            f"worker {index} instance registry bled: {sorted(get_instances())}"
        )
        # 2. Dirtied keys: likewise.
        assert get_dirtied() == set(expected_dirtied), (
            f"worker {index} dirtied set bled: {sorted(get_dirtied())}"
        )
        # 3. RenderSession: identity, not equality - a sibling's session would
        # compare unequal only by accident, but must never be the same object.
        assert current_session() is session, (
            f"worker {index} current_session() is not its own session object"
        )
        # 4. LoadCache request store: only this worker's marker, and it is a
        # distinct dict object per request.
        store = get_cache_store()
        assert set(store) == {cache_marker_for(index)}, (
            f"worker {index} cache store bled: {sorted(map(str, store))}"
        )
        sessions_seen[index] = id(store)

        # 5. The shared, read-only half: descriptors and the class registry are
        # recorded here and compared across workers after the run.
        component = _component_for(index)
        shared_sightings[index] = (
            id(type(component).__pjx_descriptor__),
            # Private module attribute accessed deliberately: asserting the
            # built-then-swap holder's identity is precisely what census point
            # 5 requires, and no public wrapper exposes it.
            id(discovery._registry),
            id(discovery._registry.mapping),
        )

    observations, errors = run_concurrent_requests(census_job, inspect=census_probe)

    fail_on_errors(errors)
    assert set(observations) == set(range(WORKERS))

    # Every worker's cache store was a distinct object, not one dict shared by
    # reference that merely happened to hold one key at snapshot time.
    assert len(set(sessions_seen.values())) == WORKERS, (
        "cache stores were not distinct objects per request"
    )

    # Workers rendering the same class must have seen one descriptor object;
    # every worker must have seen one class registry and one mapping object.
    alpha = {shared_sightings[i][0] for i in range(0, WORKERS, 2)}
    beta = {shared_sightings[i][0] for i in range(1, WORKERS, 2)}
    assert len(alpha) == 1 and len(beta) == 1, (
        "descriptors were duplicated per thread instead of shared read-only"
    )
    assert alpha != beta, "the two classes' descriptors collapsed into one object"
    assert len({s[1] for s in shared_sightings.values()}) == 1, (
        "the class registry holder differed per thread"
    )
    assert len({s[2] for s in shared_sightings.values()}) == 1, (
        "the class registry mapping was rebuilt per thread"
    )

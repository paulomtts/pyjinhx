"""Every benchmark script must still run, even though CI never times one.

Five of the nine scripts under `scripts/` were silently broken for two
milestones: #735 (absolute-path Jinja loader) left four of them building a
`template_path` from a bare filename, and #725 (`load()` became a classmethod
factory) migrated builtins, docs and examples but not this directory. Nothing
noticed, because "not in CI (timing-sensitive)" had been read as "not in CI".

Timing is what cannot be asserted here; *running* is not. Each script collapses
its sweep to the smallest entry when `PJX_BENCH_SMOKE` is set, so this executes
the whole path — build classes, write templates, render, assert its own shape —
without measuring anything.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
BENCH_SCRIPTS = sorted(p.name for p in SCRIPTS_DIR.glob("bench_*.py"))

# A smoke run is one point per sweep; the slowest is well under a second. The
# ceiling is here to fail loudly rather than hang a CI job if one regresses into
# doing real work.
TIMEOUT_SECONDS = 120


def test_every_bench_script_is_discovered():
    """Guards the glob itself: a rename that empties it must not pass silently."""
    assert len(BENCH_SCRIPTS) >= 9, BENCH_SCRIPTS


@pytest.mark.parametrize("script", BENCH_SCRIPTS)
def test_bench_script_runs(script: str):
    env = {**os.environ, "PJX_BENCH_SMOKE": "1"}
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script)],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
        env=env,
        cwd=SCRIPTS_DIR.parent,
        # Not check=True: the assertion below reports the script's own traceback,
        # which is the whole point. CalledProcessError would hide it.
        check=False,
    )
    assert result.returncode == 0, (
        f"{script} exited {result.returncode}\n"
        f"--- stdout ---\n{result.stdout[-2000:]}\n"
        f"--- stderr ---\n{result.stderr[-2000:]}"
    )
    assert result.stdout.strip(), f"{script} produced no output"


@pytest.mark.parametrize("script", BENCH_SCRIPTS)
def test_bench_script_honours_the_smoke_flag(script: str):
    """Without the collapse, a smoke run would be a full sweep and time out.

    Asserted on the source rather than by timing: the point is that the guard
    exists in every script, so a new one cannot join the suite and quietly make
    it slow.
    """
    source = (SCRIPTS_DIR / script).read_text(encoding="utf-8")
    assert "PJX_BENCH_SMOKE" in source, (
        f"{script} has no smoke guard; add one so CI can run it cheaply"
    )

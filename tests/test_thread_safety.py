"""Concurrency tests for process-wide caches (issue #240)."""

import os
import threading
import time

from pyjinhx.finder import Finder


def test_finder_concurrent_first_index_no_duplicates(tmp_path, monkeypatch):
    """N threads triggering the first index build must not corrupt the index.

    The pre-fix failure mode: both threads pass the _is_indexed check, both
    walk, and setdefault().append() doubles every entry. Duplicates cause
    find() to raise 'Ambiguous template name' for an earlier candidate
    (e.g., my_widget.html), but find_template_for_tag masks it by trying
    subsequent candidates and raising the last candidate's 'Template not found'.
    """
    (tmp_path / "my_widget.html").write_text("<div id=\"{{ id }}\"></div>")

    real_walk = os.walk

    def slow_walk(*args, **kwargs):
        # Widen the race window: yield each directory slowly so a second
        # thread reliably enters _build_index while the first is mid-walk.
        for entry in real_walk(*args, **kwargs):
            time.sleep(0.01)
            yield entry

    monkeypatch.setattr(os, "walk", slow_walk)

    finder = Finder(str(tmp_path))
    errors: list[Exception] = []
    barrier = threading.Barrier(8)

    def resolve():
        barrier.wait()
        try:
            finder.find_template_for_tag("MyWidget")
        except Exception as exc:  # noqa: BLE001 — we assert on collected errors
            errors.append(exc)

    threads = [threading.Thread(target=resolve) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert finder._index["my_widget.html"] == [str(tmp_path / "my_widget.html")]

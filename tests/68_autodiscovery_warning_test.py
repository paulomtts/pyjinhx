import logging

from pyjinhx import Renderer
from pyjinhx.tags import ComponentAutodiscover


def test_import_failure_warns(tmp_path, caplog):
    (tmp_path / "broken_probe.html").write_text('<i id="{{ id }}">x</i>')
    (tmp_path / "broken_probe.py").write_text("raise RuntimeError('boom')\n")
    original_environment = Renderer.peek_default_environment()
    ComponentAutodiscover.clear()
    try:
        Renderer.set_default_environment(str(tmp_path))
        renderer = Renderer.get_default_renderer()
        with caplog.at_level(logging.WARNING, logger="pyjinhx"):
            renderer.render('<BrokenProbe id="b1"/>')
        assert any("broken_probe.py" in r.message or "broken_probe.py" in r.getMessage() for r in caplog.records)
    finally:
        Renderer.set_default_environment(original_environment)


def test_unregistered_fallback_warns_once(tmp_path, caplog):
    (tmp_path / "ghost_probe.html").write_text('<i id="{{ id }}">x</i>')
    (tmp_path / "ghost_probe.py").write_text("VALUE = 1\n")
    original_environment = Renderer.peek_default_environment()
    ComponentAutodiscover.clear()
    try:
        Renderer.set_default_environment(str(tmp_path))
        renderer = Renderer.get_default_renderer()
        with caplog.at_level(logging.WARNING, logger="pyjinhx"):
            renderer.render('<GhostProbe id="g1"/>')
            renderer.render('<GhostProbe id="g2"/>')
        hits = [r for r in caplog.records if "GhostProbe" in r.getMessage() and "not registered" in r.getMessage()]
        assert len(hits) == 1
    finally:
        Renderer.set_default_environment(original_environment)

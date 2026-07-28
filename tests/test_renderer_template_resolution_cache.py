"""The per-class resolution walk must run once, not once per render (#240)."""

from pyjinhx import BaseComponent, Registry, Renderer
from pyjinhx.finder import Finder


def test_resolution_walk_runs_once_per_class(tmp_path, monkeypatch):
    (tmp_path / "greeting.html").write_text('<div id="{{ id }}">{{ text }}</div>')

    class Greeting(BaseComponent):
        text: str = "hi"

    # The component class's directory is this test file's dir; point the
    # loader root at tmp_path and force resolution through the finder-by-tag
    # path by monkeypatching the class directory to tmp_path.
    Finder.get_class_directory.cache_clear()
    monkeypatch.setattr(
        Finder, "get_class_directory", staticmethod(lambda klass: str(tmp_path))
    )

    Renderer.set_default_environment(str(tmp_path))

    calls = {"count": 0}
    real_get_relative = Finder.get_relative_template_paths

    def counting_get_relative(*args, **kwargs):
        calls["count"] += 1
        return real_get_relative(*args, **kwargs)

    monkeypatch.setattr(
        Finder, "get_relative_template_paths", staticmethod(counting_get_relative)
    )

    with Registry.request_scope():
        out1 = str(Greeting(id="g1").render())
        out2 = str(Greeting(id="g2").render())

    assert 'id="g1"' in out1 and 'id="g2"' in out2
    assert calls["count"] == 1

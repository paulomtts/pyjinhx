import os
import tempfile

from typing import Annotated

from jinja2 import Environment, FileSystemLoader

from pyjinhx import BaseComponent, MutationKey, ReactiveComponent
from pyjinhx.registry import Registry
from pyjinhx.renderer import Renderer


class Keys(MutationKey):
    SHELL = "shell"


def _renderer(temp_dir: str) -> Renderer:
    env = Environment(loader=FileSystemLoader(temp_dir))
    return Renderer(env, auto_id=True)


def test_singleton_reactive_tag_runs_load():
    """A bare reactive tag runs load(), populating a non-scalar field."""

    class Inner(BaseComponent):
        # Point load_template_for_component at the loader root so it can find
        # inner.html in the temp dir (the class lives in tests/unit/, which
        # Jinja2's FileSystemLoader cannot traverse to via ".." path segments).
        _pjx_template = "inner"
        text: str = ""

    class SidebarShell(ReactiveComponent, react={Keys.SHELL}):
        org_host: BaseComponent | None = None  # non-scalar; cannot ride a tag attr

        @classmethod
        def load(cls) -> "SidebarShell":
            return cls(org_host=Inner(id="org", text="acme"))

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "sidebar_shell.html"), "w") as f:
            f.write("<aside id='{{ id }}'>{{ org_host }}</aside>")
        with open(os.path.join(temp_dir, "inner.html"), "w") as f:
            f.write("<div id='{{ id }}'>{{ text }}</div>")

        with Registry.request_scope():
            rendered = str(_renderer(temp_dir).render("<SidebarShell/>"))

    assert "acme" in rendered  # load() ran; org_host rendered
    assert 'data-pjx-id="sidebar-shell"' in rendered

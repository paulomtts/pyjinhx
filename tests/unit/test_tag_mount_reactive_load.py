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


def test_keyed_reactive_tag_loads_from_key_attr():
    """A keyed tag passes its PjxKey-named attr to load() and derives kebab-key id."""
    from pyjinhx import PjxKey

    class UserCard(ReactiveComponent, react={Keys.SHELL}):
        user_id: Annotated[str, PjxKey()]
        name: str = ""

        @classmethod
        def load(cls, key: str) -> "UserCard":
            return cls(user_id=str(key), name=f"user {key}")

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "user_card.html"), "w") as f:
            f.write("<div id='{{ id }}'>{{ name }}</div>")
        with Registry.request_scope():
            rendered = str(_renderer(temp_dir).render('<UserCard user_id="42"/>'))

    assert "user 42" in rendered
    assert 'data-pjx-id="user-card-42"' in rendered
    assert 'data-pjx-load="42"' in rendered


def test_keyed_reactive_tag_missing_key_attr_raises():
    from pyjinhx import PjxKey
    import pytest

    class WidgetCard(ReactiveComponent, react={Keys.SHELL}):
        widget_id: Annotated[str, PjxKey()]

        @classmethod
        def load(cls, key: str) -> "WidgetCard":
            return cls(widget_id=str(key))

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "widget_card.html"), "w") as f:
            f.write("<div id='{{ id }}'></div>")
        with Registry.request_scope():
            with pytest.raises(ValueError, match="instance-keyed"):
                _renderer(temp_dir).render("<WidgetCard/>")


def test_scalar_attr_overrides_load_result():
    """A non-key scalar attr overrides the loaded value via validated assignment."""

    class PanelShell(ReactiveComponent, react={Keys.SHELL}):
        highlight: str = "off"

        @classmethod
        def load(cls) -> "PanelShell":
            return cls(highlight="off")

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "panel_shell.html"), "w") as f:
            f.write("<div id='{{ id }}'>{{ highlight }}</div>")
        with Registry.request_scope():
            rendered = str(
                _renderer(temp_dir).render('<PanelShell highlight="on"/>')
            )

    assert ">on<" in rendered  # tag attr won over load()'s "off"


def test_children_override_loaded_target_field():
    """Tag children override the _pjx_children_target field after load()."""

    class CardShell(ReactiveComponent, react={Keys.SHELL}):
        content: str = ""

        @classmethod
        def load(cls) -> "CardShell":
            return cls(content="loaded")

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "card_shell.html"), "w") as f:
            f.write("<section id='{{ id }}'>{{ content }}</section>")
        with Registry.request_scope():
            rendered = str(
                _renderer(temp_dir).render("<CardShell>from-children</CardShell>")
            )

    assert "from-children" in rendered
    assert "loaded" not in rendered


def test_duplicate_keyed_mount_id_raises():
    """Two keyed mounts deriving the same id raise a clear collision error."""
    from pyjinhx import PjxKey
    import pytest

    class RowCard(ReactiveComponent, react={Keys.SHELL}):
        row_id: Annotated[str, PjxKey()]

        @classmethod
        def load(cls, key: str) -> "RowCard":
            return cls(row_id=str(key))

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "row_card.html"), "w") as f:
            f.write("<div id='{{ id }}'></div>")
        with open(os.path.join(temp_dir, "page.html"), "w") as f:
            f.write('<div id="{{ id }}"><RowCard row_id="1"/><RowCard row_id="1"/></div>')
        with Registry.request_scope():
            with pytest.raises(ValueError, match="already used in this render"):
                _renderer(temp_dir).render('<Page id="page"/>')


def test_distinct_keyed_mounts_coexist():
    from pyjinhx import PjxKey

    class CellCard(ReactiveComponent, react={Keys.SHELL}):
        cell_id: Annotated[str, PjxKey()]

        @classmethod
        def load(cls, key: str) -> "CellCard":
            return cls(cell_id=str(key))

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "cell_card.html"), "w") as f:
            f.write("<div id='{{ id }}'>{{ cell_id }}</div>")
        with open(os.path.join(temp_dir, "grid.html"), "w") as f:
            f.write('<div id="{{ id }}"><CellCard cell_id="1"/><CellCard cell_id="2"/></div>')
        with Registry.request_scope():
            rendered = str(_renderer(temp_dir).render('<Grid id="grid"/>'))

    assert 'data-pjx-id="cell-card-1"' in rendered
    assert 'data-pjx-id="cell-card-2"' in rendered

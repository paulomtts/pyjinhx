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


def test_preloaded_instance_is_reused_without_reloading():
    """REUSE precedence: a route pre-load means the tag does NOT re-run load()."""
    calls = {"n": 0}

    class PreShell(ReactiveComponent, react={Keys.SHELL}):
        label: str = ""

        @classmethod
        def load(cls) -> "PreShell":
            calls["n"] += 1
            return cls(label=f"load-{calls['n']}")

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "pre_shell.html"), "w") as f:
            f.write("<div id='{{ id }}'>{{ label }}</div>")
        with Registry.request_scope():
            PreShell.load()  # pre-load: seeds the registry under "pre-shell"
            assert calls["n"] == 1
            rendered = str(
                _renderer(temp_dir).render('<PreShell id="pre-shell"/>')
            )

    assert "load-1" in rendered
    assert calls["n"] == 1  # tag reused the pre-loaded instance, no second load


def test_same_singleton_tag_loads_once_via_cache():
    """LoadCache: the same singleton mounted twice triggers one real load()."""
    calls = {"n": 0}

    class CacheShell(ReactiveComponent, react={Keys.SHELL}):
        label: str = ""

        @classmethod
        def load(cls) -> "CacheShell":
            calls["n"] += 1
            return cls(label="x")

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "cache_shell.html"), "w") as f:
            f.write("<div id='{{ id }}'>{{ label }}</div>")
        with open(os.path.join(temp_dir, "wrap.html"), "w") as f:
            # Two mounts: first bare (auto id), second explicit id to avoid collision.
            f.write('<div id="{{ id }}"><CacheShell/><CacheShell id="cache-2"/></div>')
        with Registry.request_scope():
            str(_renderer(temp_dir).render('<Wrap id="wrap"/>'))

    assert calls["n"] == 1  # LoadCache deduped the second load


def test_nested_reactive_child_auto_loads():
    """A reactive tag nested inside another component auto-loads too."""

    class NestChild(ReactiveComponent, react={Keys.SHELL}):
        msg: str = ""

        @classmethod
        def load(cls) -> "NestChild":
            return cls(msg="nested-loaded")

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "nest_child.html"), "w") as f:
            f.write("<span id='{{ id }}'>{{ msg }}</span>")
        with open(os.path.join(temp_dir, "host.html"), "w") as f:
            f.write("<div id='{{ id }}'><NestChild/></div>")
        with Registry.request_scope():
            rendered = str(_renderer(temp_dir).render('<Host id="host"/>'))

    assert "nested-loaded" in rendered


def test_non_reactive_tag_path_unchanged():
    """A plain BaseComponent tag still constructs from attrs (no load())."""

    class NonReactivePlain(BaseComponent):
        text: str = ""

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "non_reactive_plain.html"), "w") as f:
            f.write("<div id='{{ id }}'>{{ text }}</div>")
        with Registry.request_scope():
            rendered = str(
                _renderer(temp_dir).render('<NonReactivePlain id="p" text="hi"/>')
            )

    assert ">hi<" in rendered


def test_keyed_tag_key_excluded_non_key_attr_overridden():
    """Keyed path: key field is excluded from overrides; a non-key attr IS applied."""
    from pyjinhx import PjxKey

    class WidgetX(ReactiveComponent, react={Keys.SHELL}):
        widget_id: Annotated[str, PjxKey()]
        tone: str = "muted"

        @classmethod
        def load(cls, key: str) -> "WidgetX":
            return cls(widget_id=str(key), tone="muted")

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "widget_x.html"), "w") as f:
            f.write("<div id='{{ id }}'>{{ tone }}</div>")
        with Registry.request_scope():
            rendered = str(
                _renderer(temp_dir).render('<WidgetX widget_id="k1" tone="loud"/>')
            )

    assert "loud" in rendered          # non-key attr override applied
    assert "muted" not in rendered     # loaded default was replaced
    assert 'data-pjx-load="k1"' in rendered  # key is preserved in output

"""One app written in three shapes renders the same bytes in each.

The app lives under ``tests/fixtures/fewer_files``, once per shape:

- ``split`` (S): a ``.py`` class beside its ``.pjx``, ``.css`` and ``.js``.
- ``template_only`` (T): ``.pjx`` files with ``{#def#}`` headers and no Python,
  for the components a header can express.
- ``single_file`` (C): classes carrying their templates, blocks included,
  several to a module where they belong together.

Each test publishes one shape's registry at a time, so the class names the
shapes share never meet. Only auto-generated ids and asset tokens are
normalised before comparing; everything else must match byte for byte.
"""

import importlib
import re
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jinja2
import pytest
from pydantic import ValidationError

import tests.fixtures.fewer_files
from pyjinhx import BaseComponent, Slot, classless, discovery
from pyjinhx.assets import AssetMode
from pyjinhx.reactive.root_attrs import stamp_reactive_root_attrs
from pyjinhx.rendering import render
from pyjinhx.responses import PjxResponse, compose
from pyjinhx.session import RenderSession, accumulate_assets, request_scope
from tests.fixtures.fewer_files import domain

FIXTURES = Path(tests.fixtures.fewer_files.__file__).parent
SHAPES = {
    "S": FIXTURES / "split",
    "T": FIXTURES / "template_only",
    "C": FIXTURES / "single_file",
}


class Stage(BaseComponent):
    """Raw markup whose tags resolve against whichever shape is published."""

    markup: Slot = ""

    template = "<div>{{ markup }}</div>"


@pytest.fixture(autouse=True)
def fresh_app():
    domain.reset()
    yield
    domain.reset()
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None


@pytest.fixture
def no_component_calls(monkeypatch: pytest.MonkeyPatch):
    """Fail any render that reaches for ``component()`` to resolve a tag."""

    def refuse(name: str, template_dir: object = None):
        raise AssertionError(f"component({name!r}) was called")

    monkeypatch.setattr(classless, "component", refuse)


def module_name(path: Path) -> str:
    parts = path.relative_to(FIXTURES).with_suffix("").parts
    return ".".join([tests.fixtures.fewer_files.__name__, *parts])


def shape_classes(shape: str) -> dict[str, Any]:
    """Every component class the shape's modules define, by class name.

    Typed loosely: tests call each class's own factories, which the common
    base does not declare.
    """
    classes: dict[str, Any] = {}
    for path in sorted(SHAPES[shape].rglob("*.py")):
        module = importlib.import_module(module_name(path))
        for value in vars(module).values():
            if (
                isinstance(value, type)
                and issubclass(value, BaseComponent)
                and value.__module__ == module.__name__
            ):
                classes[value.__name__] = value
    return classes


def publish(shape: str) -> dict[str, Any]:
    """Make ``shape`` the live registry; its classes by name."""
    classes = shape_classes(shape)
    discovery.build_registry(SHAPES[shape], [*classes.values(), Stage])
    return classes


def page_session() -> RenderSession:
    """A session that inlines assets and stamps reactive roots, as a page does."""
    session = RenderSession()
    session.on_rendered.append(accumulate_assets)
    session.on_rendered.append(stamp_reactive_root_attrs)
    session.css_mode = AssetMode.INLINE
    session.js_mode = AssetMode.INLINE
    return session


Build = Callable[[dict[str, Any]], BaseComponent]


def render_shape(shape: str, build: Build) -> str:
    classes = publish(shape)
    session = page_session()
    with request_scope(session=session):
        return render(build(classes), session)


def staged(markup: str) -> Build:
    return lambda classes: Stage(markup=markup)


_AUTO_ID = re.compile(r"pjx-\d+")
_ASSET = re.compile(r"\s*<(style|script)\b[^>]*>(.*?)</\1>", re.DOTALL)


def normalise(html: str) -> str:
    """``html`` with auto ids renumbered in order of appearance."""
    seen: dict[str, str] = {}
    return _AUTO_ID.sub(
        lambda m: seen.setdefault(m.group(), f"pjx-{len(seen) + 1}"), html
    )


def split_assets(html: str) -> tuple[str, list[tuple[str, str]]]:
    """The markup without its inlined assets, and each asset's kind and text.

    A block's body is stripped when it is read and a sibling file is shipped
    as it is on disk, so asset text is compared stripped; the token is a
    digest of the asset's path and is dropped.
    """
    assets = [(kind, text.strip()) for kind, text in _ASSET.findall(html)]
    return _ASSET.sub("", html), assets


def render_split(shape: str, build: Build) -> tuple[str, list[tuple[str, str]]]:
    markup, assets = split_assets(render_shape(shape, build))
    return normalise(markup), assets


# Markup for every component a header can express, rendered in all three shapes.
EVERY_SHAPE = {
    "badge": '<Badge id="b1" label="New" variant="accent"/>',
    "badge-default": '<Badge id="b2" label="Old"/>',
    "button": (
        '<Button label="Save" hx_post="/save"'
        ' attrs=\'{"hx-target": "#main", "data-x": "1"}\'/>'
    ),
    "button-ghost": '<Button label="Close" kind="ghost"/>',
    "card": '<Card title="Hi" header="&lt;em&gt;sub&lt;/em&gt;">body <b>x</b></Card>',
    "card-bare": '<Card title="Bare"/>',
    "toolbar": "<Toolbar/>",
    "toolbar-actions": '<Toolbar title="Mine" actions=\'["one", "two"]\'/>',
    "status-dot": "<StatusDot/>",
    "status-dot-late": '<StatusDot tone="late"/>',
    "empty-state": '<EmptyState message="None" icon="&lt;svg&gt;&lt;/svg&gt;"/>',
    "name-field": (
        '<NameField id="n" input_id="i" label="Name" value="&lt;x&gt;"'
        ' error="Required" oob="true"/>'
    ),
}

# Markup for components that need Python, rendered in S and C.
CLASS_SHAPES = {
    "money": '<Money cents="123456" currency=" usd "/>',
    "project-name-field": '<ProjectNameField id="p" value="Launch"/>',
    "task-name-field": '<TaskNameField id="t" error="Required"/>',
    "todo-count": "<TodoCount/>",
    "todo-row": '<TodoRow todo_id="3"/>',
    "todo-list": '<TodoList id="l" todo_ids="[1, 2]"/>',
    "todo-list-empty": '<TodoList id="l"/>',
}


@pytest.mark.parametrize("markup", EVERY_SHAPE.values(), ids=EVERY_SHAPE.keys())
def test_a_component_renders_the_same_in_every_shape(markup, no_component_calls):
    split = render_split("S", staged(markup))
    assert render_split("T", staged(markup)) == split
    assert render_split("C", staged(markup)) == split


@pytest.mark.parametrize("markup", CLASS_SHAPES.values(), ids=CLASS_SHAPES.keys())
def test_a_component_with_python_renders_the_same_split_or_single_file(markup):
    assert render_split("C", staged(markup)) == render_split("S", staged(markup))


def build_page(classes: dict[str, Any]) -> BaseComponent:
    return classes["TodoPage"].build(project="Launch <2026>")


def test_the_full_page_renders_the_same_split_or_single_file():
    split = render_split("S", build_page)
    assert render_split("C", build_page) == split


def test_the_full_page_uses_every_component_and_resolves_every_tag():
    markup, _ = render_split("S", build_page)
    assert not re.search(r"<[A-Z]", markup)
    for marker in [
        "badge--accent",
        "todo-count",
        "btn--ghost",
        "card__header",
        "name-field",
        "todo-row--open",
        "dot--busy",
        "money",
        "empty-state",
        "Launch &lt;2026&gt;",
        "Order &lt;snacks&gt;",
    ]:
        assert marker in markup


def test_the_full_page_ships_the_same_assets_in_the_same_order():
    _, split = render_split("S", build_page)
    _, single_file = render_split("C", build_page)
    assert single_file == split
    assert [kind for kind, _ in split] == ["style"] * 5 + ["script"]


def test_the_template_only_shape_ships_the_same_assets_as_split():
    markup = "".join(EVERY_SHAPE.values())
    _, split = render_split("S", staged(markup))
    _, template_only = render_split("T", staged(markup))
    assert template_only == split
    assert len(split) == 4


# Partials: what an htmx request swaps in without the page around it.


def build_row(classes: dict[str, Any]) -> BaseComponent:
    return classes["TodoRow"].load(3)


def build_name_error(classes: dict[str, Any]) -> BaseComponent:
    return classes["TaskNameField"](
        id="task-name-field", value="", error="Required", oob=True
    )


@pytest.mark.parametrize("build", [build_row, build_name_error], ids=["row", "oob"])
def test_a_partial_renders_the_same_split_or_single_file(build):
    assert render_split("C", build) == render_split("S", build)


_MOUNTED_ROOT = re.compile(
    r'data-pjx-id="([^"]*)" data-pjx-type="([^"]*)" data-pjx-hash="([^"]*)"'
    r'(?: data-pjx-load="([^"]*)")?'
)


def mounted(html: str) -> list[dict[str, object]]:
    """The manifest a browser holding ``html`` would send back."""
    return [
        {"id": id_, "type": type_, "hash": hash_, "load": load or None}
        for id_, type_, hash_, load in _MOUNTED_ROOT.findall(html)
    ]


def delta_after_toggle(shape: str) -> str:
    """The response body after todo 1 is ticked, for a browser showing the page."""
    domain.reset()
    page = render_shape(shape, build_page)
    session = page_session()
    session.pjx_mounted = mounted(page)
    with request_scope(session=session):
        domain.toggle(1)
        response = compose(None, session=session)
    assert isinstance(response, PjxResponse)
    return response.body


def test_dirtying_the_key_swaps_the_same_regions_split_or_single_file():
    split, split_assets_ = split_assets(delta_after_toggle("S"))
    single_file, single_file_assets = split_assets(delta_after_toggle("C"))
    assert normalise(single_file) == normalise(split)
    assert single_file_assets == split_assets_
    assert split.count("hx-swap-oob") == 2
    assert 'id="todo-count"' in split
    assert "2 tasks left" in split
    assert "todo-row--done" in split


# Errors name the file and line the author has to open, whatever the shape.


def line_of(path: Path, text: str) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    return next(number for number, line in enumerate(lines, 1) if text in line)


BROKEN = {
    "S": (
        SHAPES["S"] / "broken/broken_note.pjx",
        SHAPES["S"] / "broken/stray_lookup.pjx",
    ),
    "T": (
        SHAPES["T"] / "broken/broken_note.pjx",
        SHAPES["T"] / "broken/stray_lookup.pjx",
    ),
    "C": (SHAPES["C"] / "broken/broken.py",) * 2,
}


@pytest.mark.parametrize("shape", SHAPES)
def test_a_syntax_error_names_the_file_and_line_it_is_on(shape):
    path = BROKEN[shape][0]
    with pytest.raises(jinja2.TemplateSyntaxError) as caught:
        render_shape(shape, staged("<BrokenNote/>"))
    assert caught.value.filename == str(path)
    assert caught.value.lineno == line_of(path, "{% if %}")


@pytest.mark.parametrize("shape", SHAPES)
def test_a_render_error_traceback_names_the_file_and_line_it_is_on(shape):
    path = BROKEN[shape][1]
    with pytest.raises(jinja2.UndefinedError) as caught:
        render_shape(shape, staged("<StrayLookup/>"))
    frames = traceback.extract_tb(caught.tb)
    frame = next(f for f in frames if "template code" in f.name)
    assert (frame.filename, frame.lineno) == (
        str(path),
        line_of(path, "{{ nothing.here }}"),
    )


def prop_errors(shape: str, markup: str) -> list[tuple[object, ...]]:
    with pytest.raises(ValidationError) as caught:
        render_shape(shape, staged(markup))
    assert caught.value.title == "Badge"
    return [(e["loc"], e["type"], e["msg"]) for e in caught.value.errors()]


@pytest.mark.parametrize(
    "markup",
    ['<Badge id="b" label="x" variant="loud"/>', '<Badge label="x"/>'],
    ids=["bad-literal", "missing-id"],
)
def test_a_bad_prop_is_refused_the_same_way_in_every_shape(markup):
    split = prop_errors("S", markup)
    assert prop_errors("T", markup) == split
    assert prop_errors("C", markup) == split


def test_a_bad_header_names_its_template(tmp_path):
    (tmp_path / "badge.pjx").write_text("{#def id: str, label: str = nope #}<b></b>")
    discovery.build_registry(tmp_path, [Stage])
    with pytest.raises(ValueError, match=re.escape(str(tmp_path / "badge.pjx"))):
        render(Stage(markup='<Badge id="b"/>'))


# What each shape is made of.


def test_the_template_only_shape_has_no_python():
    assert list(SHAPES["T"].rglob("*.py")) == []


def test_the_single_file_shape_keeps_each_component_in_its_module():
    loose = [
        p.name for p in SHAPES["C"].rglob("*") if p.suffix in {".pjx", ".css", ".js"}
    ]
    assert loose == ["card.css"]
    for cls in shape_classes("C").values():
        descriptor = cls.__pjx_descriptor__
        assert descriptor.template_path.suffix == ".py", cls
        assert descriptor.inline_class is not None, cls


def test_the_single_file_shape_puts_several_components_in_a_module():
    modules = [cls.__module__ for cls in shape_classes("C").values()]
    assert max(modules.count(name) for name in modules) == 3


def test_a_subclass_family_renders_its_parents_inline_template():
    classes = shape_classes("C")
    for name in ["ProjectNameField", "TaskNameField"]:
        assert classes[name].__pjx_descriptor__.inline_class == "NameField"

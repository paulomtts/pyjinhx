"""L1.4.6 — the cross-cutting matrix for the whole classless surface.

Open subclass (#374), {#def#} parse (#375), class generation (#376), the stale
header warning (#377) and the component() factory (#378) each have their own
unit file. This one covers only what those files cannot see on their own: the
places two of those surfaces meet, and the render path none of them walks.
"""

import logging
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

from pyjinhx2 import discovery
from pyjinhx2.classless import component
from pyjinhx2.component import BaseComponent, OpenComponent
from pyjinhx2.props_header import build_component_class, parse_props_header
from pyjinhx2.render import render_level
from pyjinhx2.segments import serialize
from pyjinhx2.session import RenderSession


@pytest.fixture(autouse=True)
def reset_registry():
    """Each test starts from an empty published mapping."""
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None
    yield
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None


def write_template(directory: Path, tag: str, source: str) -> Path:
    """Write ``source`` to ``<directory>/<tag>.pjx`` and return the path."""
    path = directory / f"{tag}.pjx"
    path.write_text(source, encoding="utf-8")
    return path


def absolute_session() -> RenderSession:
    """A session that can load a descriptor's absolute template path.

    A classless class's descriptor names its template by absolute path, and
    Jinja's loader resolves such a name against a root of "/" — so the tests
    render the real generated class against its real file on disk instead of
    swapping in a descriptor that points somewhere loadable.
    """
    return RenderSession(template_dir="/")


def _three_classes(tmp_path: Path) -> dict[str, type[OpenComponent]]:
    """One class per construction path, all three built in the same session.

    The point is that they are indistinguishable where ADR 0006 says they must
    be: header-built, placeholder and hand-written all open the same way.
    """
    write_template(tmp_path, "card", '{#def title: str = "hi" #}<div>{{ title }}</div>')
    write_template(tmp_path, "badge", "<div>plain</div>")

    class Panel(OpenComponent):
        title: str = "hi"

    return {
        "headed": component("Card", template_dir=tmp_path),
        "placeholder": component("Badge", template_dir=tmp_path),
        "handwritten": Panel,
    }


def test_every_construction_path_lands_on_the_open_base(tmp_path):
    """ADR 0006: a class that accepts extras subclasses OpenComponent, always."""
    for label, cls in _three_classes(tmp_path).items():
        assert issubclass(cls, OpenComponent), label
        assert cls.model_config.get("extra") == "allow", label


def test_every_construction_path_keeps_the_strict_core_underneath(tmp_path):
    """Open is an opt-in *subclass*, so the strict core is still the ancestor."""
    for label, cls in _three_classes(tmp_path).items():
        assert issubclass(cls, BaseComponent), label
        assert cls is not BaseComponent, label
        assert BaseComponent.model_config.get("extra") != "allow"


def test_every_construction_path_takes_an_undeclared_attribute(tmp_path):
    """Extras parity: the three paths agree on where an unknown key lands."""
    for label, cls in _three_classes(tmp_path).items():
        instance = cls(data_role="banner")  # pyright: ignore[reportCallIssue]
        assert instance.model_extra == {"data_role": "banner"}, label

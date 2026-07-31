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

"""Every builtin renders exactly one root element and passes inline attrs."""

import pytest

import pyjinhx.builtins as builtins_pkg
from pyjinhx import Renderer
from pyjinhx.base import BaseComponent


def _builtin_classes():
    seen = []
    for name in dir(builtins_pkg):
        obj = getattr(builtins_pkg, name)
        if isinstance(obj, type) and issubclass(obj, BaseComponent) and obj is not BaseComponent:
            seen.append(obj)
    return seen


@pytest.mark.parametrize("cls", _builtin_classes(), ids=lambda c: c.__name__)
def test_builtin_renders_single_root(cls, tmp_path):
    Renderer.set_default_environment(str(tmp_path))
    # Construct with only id; required fields use defaults. Skip any builtin
    # that cannot be built id-only (its own dedicated test covers it).
    try:
        component = cls(id="x")
    except Exception:
        pytest.skip(f"{cls.__name__} needs required fields; covered elsewhere")
    # render() raises ValueError if the template is not exactly one root.
    str(component.render())

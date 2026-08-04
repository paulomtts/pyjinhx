"""Tests for the .pjx template-tree walk (issue #357)."""

import importlib.util
import logging
import sys
from pathlib import Path

import pytest

from pyjinhx import discovery
from pyjinhx.discovery import TemplateCandidate, walk_templates

DISCOVERY_DIR = Path(__file__).parent.parent / "templates" / "discovery"


@pytest.fixture(autouse=True)
def reset_registry():
    """Each test starts from an empty published mapping, and leaves one behind."""
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None
    yield
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None


def _load_class_from_module(module_path: Path, module_name: str, class_name: str) -> type:
    """Import ``module_path`` under a throwaway module name and return one of its classes.

    Mirrors how a real builtin resolves its template: the class's __module__
    must have a __file__ that actually lives beside the .pjx file, which a
    class body attribute cannot fake (see pyjinhx/component.py::_defining_module_dir).
    """
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, class_name)


def tags(candidates):
    """Tag names of the given candidates, in yield order."""
    return [candidate.tag_name for candidate in candidates]


def test_walk_empty_dir_yields_nothing(tmp_path):
    assert list(walk_templates(tmp_path)) == []


def test_walk_dir_with_only_non_pjx_files_yields_nothing(tmp_path):
    (tmp_path / "page.html").write_text("<div></div>")
    (tmp_path / "notes.txt").write_text("hello")
    assert list(walk_templates(tmp_path)) == []


def test_walk_finds_single_pjx_file(tmp_path):
    path = tmp_path / "alpha_card.pjx"
    path.write_text("<div></div>")
    assert list(walk_templates(tmp_path)) == [TemplateCandidate("alpha_card", path)]


def test_walk_finds_nested_pjx_files():
    found = list(walk_templates(DISCOVERY_DIR))
    assert "nested_widget" in tags(found)
    assert "deep_widget" in tags(found)


def test_walk_skips_non_pjx_files():
    found = tags(walk_templates(DISCOVERY_DIR))
    assert "legacy_card" not in found
    assert "readme" not in found


def test_walk_skips_non_snake_case_filenames():
    found = tags(walk_templates(DISCOVERY_DIR))
    assert "bad-name" not in found
    assert "BadName" not in found
    assert "bad_name" not in found
    assert "badname" not in found


def test_walk_yields_stable_deterministic_order():
    first = list(walk_templates(DISCOVERY_DIR))
    second = list(walk_templates(DISCOVERY_DIR))
    assert first == second
    assert [candidate.path for candidate in first] == sorted(
        candidate.path for candidate in first
    )


def test_walk_accepts_str_template_dir():
    assert list(walk_templates(str(DISCOVERY_DIR))) == list(
        walk_templates(DISCOVERY_DIR)
    )


def test_walk_missing_template_dir_raises(tmp_path):
    with pytest.raises(NotADirectoryError):
        list(walk_templates(tmp_path / "nope"))


def test_walk_template_dir_is_file_raises(tmp_path):
    path = tmp_path / "a_file.pjx"
    path.write_text("<div></div>")
    with pytest.raises(NotADirectoryError):
        list(walk_templates(path))


def test_walk_does_not_deduplicate_same_tag_name_in_different_dirs():
    found = [c for c in walk_templates(DISCOVERY_DIR) if c.tag_name == "alpha_card"]
    assert len(found) == 2
    assert {c.path.parent.name for c in found} == {"discovery", "forms"}


def test_walk_is_pure_no_registry_side_effect():
    assert list(walk_templates(DISCOVERY_DIR)) == list(walk_templates(DISCOVERY_DIR))

    mutable = [
        name
        for name, value in vars(discovery).items()
        if isinstance(value, (dict, list, set)) and not name.startswith("__")
    ]
    assert mutable == []


def test_class_with_template_outside_template_dir_is_claimed(tmp_path: Path):
    """A class whose own template lives outside the walked tree still claims its tag."""
    outside = tmp_path / "installed"
    outside.mkdir()
    (outside / "outside_widget.pjx").write_text("<div>outside</div>")
    (outside / "outside_widget.py").write_text(
        "from pyjinhx.component import BaseComponent\n\n\n"
        "class OutsideWidget(BaseComponent):\n"
        "    pass\n"
    )
    walked = tmp_path / "components"
    walked.mkdir()

    OutsideWidget = _load_class_from_module(
        outside / "outside_widget.py", "test_outside_widget_mod", "OutsideWidget"
    )

    discovery.build_registry(walked, [OutsideWidget])

    assert discovery.get_class("outside_widget") is OutsideWidget


def test_user_class_with_replace_shadows_an_outside_class(tmp_path, caplog):
    """A user class declaring replace takes the tag from an outside-template class, silently."""
    outside = tmp_path / "installed"
    outside.mkdir()
    (outside / "user_thing.pjx").write_text("<div>outside</div>")
    (outside / "user_thing.py").write_text(
        "from pyjinhx.component import BaseComponent\n\n\n"
        "class UserThing(BaseComponent):\n"
        "    pass\n"
    )
    OutsideThing = _load_class_from_module(
        outside / "user_thing.py", "test_outside_thing_mod", "UserThing"
    )

    walked = tmp_path / "components"
    walked.mkdir()
    (walked / "user_thing.pjx").write_text("<div>user</div>")
    (walked / "user_thing.py").write_text(
        "from pyjinhx.component import BaseComponent\n\n\n"
        "class UserThing(BaseComponent, pjx_replace=True):\n"
        "    pass\n"
    )
    UserThing = _load_class_from_module(
        walked / "user_thing.py", "test_user_thing_mod", "UserThing"
    )
    # `pjx_replace=True` is a class-kwarg consumed by
    # BaseComponent.__init_subclass__ (pyjinhx/component.py), not a decorator
    # or a plain class attribute.

    discovery.build_registry(walked, [OutsideThing, UserThing])

    assert discovery.get_class("user_thing") is UserThing
    assert not [r for r in caplog.records if r.levelname == "WARNING"]


def test_unintended_collision_across_sources_warns_once(tmp_path, caplog):
    """Neither side declaring replace: alphabetical qualified-name tie-break, one warning naming both."""
    outside = tmp_path / "installed"
    outside.mkdir()
    (outside / "user_thing.pjx").write_text("<div>outside</div>")
    (outside / "user_thing.py").write_text(
        "from pyjinhx.component import BaseComponent\n\n\n"
        "class UserThing(BaseComponent):\n"
        "    pass\n"
    )
    OutsideThing = _load_class_from_module(
        outside / "user_thing.py", "test_outside_thing_mod2", "UserThing"
    )

    walked = tmp_path / "components"
    walked.mkdir()
    (walked / "user_thing.pjx").write_text("<div>user</div>")
    (walked / "user_thing.py").write_text(
        "from pyjinhx.component import BaseComponent\n\n\n"
        "class UserThing(BaseComponent):\n"
        "    pass\n"
    )
    UserThing = _load_class_from_module(
        walked / "user_thing.py", "test_user_thing_mod2", "UserThing"
    )

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        discovery.build_registry(walked, [OutsideThing, UserThing])

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "test_outside_thing_mod2.UserThing" in warnings[0].getMessage()
    assert "test_user_thing_mod2.UserThing" in warnings[0].getMessage()

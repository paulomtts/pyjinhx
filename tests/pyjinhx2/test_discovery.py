"""Tests for the .pjx template-tree walk (issue #357)."""

from pathlib import Path

import pytest

from pyjinhx2.discovery import TemplateCandidate, walk_templates

DISCOVERY_DIR = Path(__file__).parent.parent / "templates" / "discovery"


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
    from pyjinhx2 import discovery

    mutable = [
        name
        for name, value in vars(discovery).items()
        if isinstance(value, (dict, list, set)) and not name.startswith("__")
    ]
    assert mutable == []

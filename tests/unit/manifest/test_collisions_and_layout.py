"""Tests for manifest name collisions, module layout and the remaining entry details."""

import json
from pathlib import Path

from pyjinhx import manifest
from pyjinhx.document import scanner
from tests.unit.manifest._helpers import (
    GOOD,
    _abs,
    _at,
    _components,
    _document,
    _one,
    _stdin,
    _write,
)


def _collisions(tree, **files: str) -> list[dict]:
    _write(tree, {f"app/ui/{name}.py": text for name, text in files.items()})
    result = manifest.describe([Path("app")])
    return [d for d in result["diagnostics"] if d["code"] == "tag-collision"]


def test_every_component_has_a_name_an_id_and_a_replaces_flag(tree):
    (tree / "app/ui/swap.py").write_text(
        "class Swap(BaseComponent, pjx_replace=True):\n    template = '<p></p>'\n"
    )
    found = _components(tree)

    assert found["TodoCount"]["name"] == "todo_count"
    assert found["TodoCount"]["id"] == _abs("app/ui/todo_count.pjx") + "#TodoCount"
    assert found["Badge"]["id"] == _abs("app/ui/badge.pjx")
    assert found["Chip"]["id"] == _abs("app/ui/chip.py") + "#Chip"
    assert found["Card"]["id"] == _abs("app/ui/card.py") + "#Card"
    assert found["Swap"]["replaces"] is True
    assert found["Chip"]["replaces"] is False


def test_the_ids_of_a_tree_are_unique(tree):
    result = manifest.describe([Path("app")])

    ids = [c["id"] for c in result["components"]]
    assert len(ids) == len(set(ids))


def test_two_components_with_one_name_are_a_warning_on_each(tree):
    found = _collisions(
        tree,
        other="class Chip:\n    template = '<i></i>'\n",
    )

    assert {(d["path"], d["severity"]) for d in found} == {
        (_abs("app/ui/chip.py"), "warning"),
        (_abs("app/ui/other.py"), "warning"),
    }


def test_one_component_that_replaces_settles_a_collision(tree):
    found = _collisions(
        tree,
        other="class Chip(pjx_replace=True):\n    template = '<i></i>'\n",
    )

    assert found == []


def test_the_builtins_are_listed_and_marked(tree):
    result = manifest.describe([Path("app")])

    builtins = [c for c in result["components"] if c["builtin"]]
    assert any(c["tag"] == "PJXBadge" for c in builtins)
    assert all(not c["builtin"] for c in result["components"] if c["tag"] == "Chip")
    assert result["diagnostics"] == [
        d for d in result["diagnostics"] if d["code"].startswith("stub-")
    ]


def test_scanning_the_package_does_not_list_a_builtin_twice(monkeypatch):
    root = Path(manifest.__file__).parent
    monkeypatch.chdir(root.parent)

    result = manifest.describe([root])

    ids = [c["id"] for c in result["components"]]
    assert len(ids) == len(set(ids))
    assert any(c["builtin"] for c in result["components"])


def test_a_package_layout_names_modules_by_the_deepest_sys_path_entry(tmp_path):
    (tmp_path / "src" / "ns" / "ui").mkdir(parents=True)
    path = tmp_path / "src" / "ns" / "ui" / "card.pjx"

    assert scanner.module_name_for(path) == "card"
    assert scanner.module_name_for(path, [str(tmp_path / "src")]) == "ns.ui.card"
    assert (
        scanner.module_name_for(
            path, [str(tmp_path / "src"), str(tmp_path / "src" / "ns")]
        )
        == "ui.card"
    )
    assert scanner.module_name_for(path, [str(tmp_path / "other")]) is None


def test_sys_path_names_the_class_module_in_the_manifest(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"src/ns/card.pjx": GOOD})

    manifest.main(["--sys-path", "src", "src"])

    components = json.loads(capsys.readouterr().out)["components"]
    card = next(c for c in components if not c["builtin"])
    assert card["class"]["module"] == "ns.card"


def test_a_split_component_knows_when_its_document_has_a_stale_header(tree):
    (tree / "app/ui/card.pjx").write_text("{#def title: str #}\n<p></p>\n")

    found = _components(tree)

    assert found["Card"]["has_stale_def_header"] is True
    assert found["Chip"]["has_stale_def_header"] is False


def test_strict_is_read_from_the_class_body_and_null_when_not_stated(tree):
    _write(
        tree,
        {
            "app/ui/loose.py": "class Loose:\n"
            "    model_config = ConfigDict(extra='allow')\n"
            "    template = '<p></p>'\n",
            "app/ui/tight.py": "class Tight:\n"
            "    model_config = {'extra': 'forbid'}\n"
            "    template = '<p></p>'\n",
        },
    )

    found = _components(tree)

    assert (found["Loose"]["strict"], found["Tight"]["strict"]) == (False, True)
    assert found["Chip"]["strict"] is None
    assert found["Badge"]["strict"] is False


def test_sibling_assets_are_listed_when_they_exist(tree):
    (tree / "app/ui/chip.css").write_text("")
    (tree / "app/ui/todo_count.js").write_text("")

    found = _components(tree)

    assert found["Chip"]["assets"] == {"css": _abs("app/ui/chip.css"), "js": None}
    assert found["TodoCount"]["assets"] == {
        "css": None,
        "js": _abs("app/ui/todo_count.js"),
    }


def test_a_document_with_a_python_block_that_does_not_scan_still_has_an_entry(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "card.pjx").write_text("{#python\nclass Card:\n    pass\n<p></p>\n")

    result = manifest.describe([Path(".")])

    mine = [c for c in result["components"] if not c["builtin"]]
    assert [(c["tag"], c["kind"], c["class"]) for c in mine] == [
        ("Card", "pjx-python", None)
    ]
    assert [d["code"] for d in result["diagnostics"]] == ["unclosed-block"]


def test_a_spaced_opener_and_prose_are_templates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "card.pjx").write_text("{#python is nice #}\n<p></p>\n")
    (tmp_path / "chip.pjx").write_text("{# python\nclass Chip: pass\n#}\n<p></p>\n")

    result = manifest.describe([Path(".")])

    mine = {c["tag"]: c for c in result["components"] if not c["builtin"]}
    assert mine["Card"]["kind"] == "template"
    assert mine["Chip"]["kind"] == "template"
    diagnostics = {
        Path(d["path"]).name: d
        for d in result["diagnostics"]
        if d["path"].endswith(".pjx")
    }
    assert diagnostics == {}


def test_an_indented_python_comment_is_not_a_document(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "card.pjx").write_text("<p></p>\n  {#python\n  x = 1\n  #}\n")

    result = manifest.describe([Path(".")])

    assert [c["kind"] for c in result["components"] if not c["builtin"]] == ["template"]


def test_a_python_block_document_no_sys_path_entry_holds_has_no_module(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"src/ns/card.pjx": GOOD})

    result = manifest.describe([Path("src")], [Path("other")])

    card = next(c for c in result["components"] if not c["builtin"])
    assert card["class"]["module"] is None
    assert "no-module-name" in [d["code"] for d in result["diagnostics"]]


def test_a_package_init_module_is_named_for_its_package(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")

    assert scanner.module_name_for(tmp_path / "pkg" / "__init__.py") == "pkg"


def test_a_diagnostic_in_a_py_template_has_the_modules_column(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "chip.py").write_text(
        'class Chip:\n    template = """\n        <p></p>\n        {#css x #}\n'
        '        {#css\n        a {}\n        #}\n        {#css\n        b {}\n        #}\n    """\n'
    )

    found = _one(manifest.describe([Path("chip.py")])["diagnostics"], "second-block")

    assert _at(found)[1] == 8


def test_a_range_ends_where_it_starts_or_later(tree):
    (tree / "app/ui/early.pjx").write_text('{#python\nx = "#}"\n#}\n<p></p>\n')

    for diagnostic in manifest.describe([Path("app")])["diagnostics"]:
        start, end = diagnostic["range"]["start"], diagnostic["range"]["end"]
        assert (end["line"], end["column"]) >= (start["line"], start["column"])


def test_an_unhashable_literal_in_a_header_or_a_field_does_not_stop_the_run(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    _write(
        tmp_path,
        {
            "bad_header.pjx": "{#def f: int = {[1]: 2} #}\n<p></p>\n",
            "bad_field.py": "class BadField:\n    f: Literal[{[1]: 2}] = 1\n    template = '<p></p>'\n",
            "fine.pjx": "<p></p>\n",
        },
    )

    result = manifest.describe([Path(".")])

    mine = {c["tag"]: c for c in result["components"] if not c["builtin"]}
    assert set(mine) == {"BadHeader", "BadField", "Fine"}
    assert mine["BadField"]["props"][0]["literal_values"] is None
    assert [d["code"] for d in result["diagnostics"]] == ["def-header-invalid"]


def test_an_unexpected_failure_in_one_file_is_a_diagnostic_for_that_file(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, {"bad.pjx": "<p></p>\n", "fine.pjx": "<p></p>\n"})
    real = manifest._template_component

    def explode(project, document):
        if document.path.stem == "bad":
            raise RuntimeError("boom")
        return real(project, document)

    monkeypatch.setattr(manifest, "_template_component", explode)

    result = manifest.describe([Path(".")])

    assert [c["tag"] for c in result["components"] if not c["builtin"]] == ["Fine"]
    found = _one(result["diagnostics"], "internal-error")
    assert (found["path"], found["severity"]) == (_abs("bad.pjx"), "error")
    assert "boom" in found["message"]


def test_a_stdin_buffer_reports_each_collision_once(tree, monkeypatch, capsys):
    _stdin(
        monkeypatch,
        "class Chip:\n    template = '<i></i>'\n\n\nclass Chip:\n    template = '<b></b>'\n",
    )

    manifest.main(["--stdin", "--filename", "app/ui/other.py"])

    result = json.loads(capsys.readouterr().out)
    # Two classes in the buffer, each warned about once.
    assert [d["code"] for d in result["diagnostics"]] == ["tag-collision"] * 2


def test_a_collision_with_a_builtin_is_reported_on_the_user_file_only(tree):
    found = _collisions(tree, mine="class PjxBadge:\n    template = '<i></i>'\n")

    assert {d["path"] for d in found} == {_abs("app/ui/mine.py")}


def test_strict_is_null_when_no_class_was_found_and_false_only_for_templates(tree):
    (tree / "app/ui/nope.pjx").write_text(
        "{#python\nclass Other:\n    pass\n#}\n<p></p>\n"
    )

    found = _components(tree)

    assert found["Nope"]["strict"] is None
    assert found["Badge"]["strict"] is False


def test_a_zero_width_range_is_widened_to_the_end_of_its_line(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    unclosed = _one(
        _document(tmp_path, "{#def a, ( #}\n<p></p>\n"), "def-header-invalid"
    )
    syntax = _one(
        _document(tmp_path, "{#python\nx = (\n#}\n<p></p>\n", "card.pjx"),
        "python-syntax-error",
    )

    for found in (unclosed, syntax):
        assert found["range"]["end"] != found["range"]["start"], found


def test_a_template_is_named_by_its_stem(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "x_2.pjx").write_text("<p></p>\n")

    result = manifest.describe([Path(".")])

    assert next(c for c in result["components"] if c["tag"] == "X2")["name"] == "x_2"


def test_a_raw_protected_example_is_a_template_not_a_document(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "guide.pjx").write_text(
        "{% raw %}\n{#python\nx = 1\n#}\n{% endraw %}\n<p></p>\n"
    )

    result = manifest.describe([Path(".")])

    mine = {c["tag"]: c for c in result["components"] if not c["builtin"]}
    assert mine["Guide"]["kind"] == "template"
    assert not [d for d in result["diagnostics"] if d["path"].endswith(".pjx")]

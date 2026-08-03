"""Tests for the absolute-path Jinja loader that RenderSession installs."""

import os
from pathlib import Path

import jinja2
import pytest

from pyjinhx.session import AbsolutePathLoader, RenderSession


@pytest.fixture
def template_file(tmp_path: Path) -> Path:
    path = tmp_path / "card.pjx"
    path.write_text("<div>hello</div>")
    return path


def test_an_absolute_path_loads_its_contents_as_source(template_file: Path):
    loader = AbsolutePathLoader()
    source, name, _uptodate = loader.get_source(jinja2.Environment(), str(template_file))
    assert source == "<div>hello</div>"
    assert name == str(template_file)


def test_a_missing_absolute_path_raises_template_not_found(tmp_path: Path):
    loader = AbsolutePathLoader()
    with pytest.raises(jinja2.TemplateNotFound):
        loader.get_source(jinja2.Environment(), str(tmp_path / "nope.pjx"))


def test_a_relative_name_is_not_resolved_against_cwd(tmp_path: Path, monkeypatch):
    (tmp_path / "card.pjx").write_text("<div>hello</div>")
    monkeypatch.chdir(tmp_path)
    loader = AbsolutePathLoader()
    with pytest.raises(jinja2.TemplateNotFound):
        loader.get_source(jinja2.Environment(), "card.pjx")


def test_uptodate_is_true_while_the_file_is_unchanged(template_file: Path):
    loader = AbsolutePathLoader()
    _source, _name, uptodate = loader.get_source(jinja2.Environment(), str(template_file))
    assert uptodate() is True


def test_uptodate_is_false_after_the_mtime_changes(template_file: Path):
    loader = AbsolutePathLoader()
    _source, _name, uptodate = loader.get_source(jinja2.Environment(), str(template_file))
    stat = template_file.stat()
    os.utime(template_file, (stat.st_atime, stat.st_mtime + 10))
    assert uptodate() is False


def test_uptodate_is_false_after_the_file_is_deleted(template_file: Path):
    loader = AbsolutePathLoader()
    _source, _name, uptodate = loader.get_source(jinja2.Environment(), str(template_file))
    template_file.unlink()
    assert uptodate() is False


def test_a_session_environment_loads_a_template_by_absolute_path(template_file: Path):
    session = RenderSession()
    template = session.jinja_env.get_template(str(template_file))
    assert template.render() == "<div>hello</div>"


def test_a_bare_request_scope_can_render_a_builtin():
    """The #728 regression: no template_dir configured anywhere, builtins still render."""
    from pyjinhx.builtins import PJXCardHeader
    from pyjinhx.session import request_scope

    with request_scope():
        html = PJXCardHeader(title="x").render()

    assert "x" in html

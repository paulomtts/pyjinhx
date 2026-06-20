import pytest
from jinja2 import DictLoader, Environment
from jinja2.exceptions import TemplateNotFound

from pyjinhx import BaseComponent
from pyjinhx.renderer import Renderer
from pyjinhx.tags import _BUILTIN_TAG_NAMES, _missing_template_error


def test_missing_template_file():
    class MissingTemplateComponent(BaseComponent):
        text: str

    component = MissingTemplateComponent(id="missing-1", text="Test")

    with pytest.raises(TemplateNotFound):
        component.render()


def test_non_filesystem_loader_error():
    class DictLoaderComponent(BaseComponent):
        text: str

    dict_loader = DictLoader({"template.html": "<div>{{ text }}</div>"})
    env = Environment(loader=dict_loader)
    original_environment = Renderer.peek_default_environment()
    Renderer.set_default_environment(env)

    component = DictLoaderComponent(id="test-1", text="Test")

    with pytest.raises(ValueError, match="Jinja2 loader must be a FileSystemLoader"):
        component.render()

    Renderer.set_default_environment(original_environment)


def test_missing_template_error_hints_at_builtin_import():
    error = _missing_template_error("PJXTooltip")

    assert isinstance(error, FileNotFoundError)
    assert "from pyjinhx.builtins import PJXTooltip" in str(error)


def test_missing_template_error_lists_real_candidates():
    error = _missing_template_error("UserCard")

    assert str(error) == (
        "No template found for <UserCard>. Expected one of: "
        "user_card.pjx, user-card.pjx, user_card.html, user-card.html, "
        "user_card.jinja, user-card.jinja"
    )


def test_builtin_tag_names_match_builtins_all():
    import pyjinhx.builtins

    assert _BUILTIN_TAG_NAMES == frozenset(pyjinhx.builtins.__all__)

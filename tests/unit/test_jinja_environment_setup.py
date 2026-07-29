import os
import pytest
from jinja2 import Environment, FileSystemLoader, DictLoader
from jinja2.exceptions import TemplateNotFound

from pyjinhx.renderer import Renderer, _PjxContext, get_loader_root


@pytest.fixture(autouse=True)
def reset_default_environment():
    """Reset Renderer to clean state before each test."""
    original = Renderer.peek_default_environment()
    yield
    # Restore original state after test
    Renderer.set_default_environment(original)


def test_auto_detect_root_when_none_set():
    """When no environment is explicitly set, get_default_environment auto-detects root."""
    # Reset to clean state
    Renderer.set_default_environment(None)

    # Peek should return None immediately after reset
    assert Renderer.peek_default_environment() is None

    # get_default_environment should create one with auto-detected root
    env = Renderer.get_default_environment()
    assert env is not None
    assert isinstance(env.loader, FileSystemLoader)
    assert isinstance(env.loader.searchpath, list)
    assert len(env.loader.searchpath) > 0

    # After creation, peek should return the same environment
    assert Renderer.peek_default_environment() is env


def test_autoescape_enabled_by_default():
    """Autoescape is enabled=True in the default environment."""
    Renderer.set_default_environment(None)
    env = Renderer.get_default_environment()

    assert env.autoescape is True


def test_default_environment_has_custom_context_class():
    """The default environment has _PjxContext wired as context_class."""
    Renderer.set_default_environment(None)
    env = Renderer.get_default_environment()

    assert env.context_class is _PjxContext


def test_set_default_environment_none_resets_to_auto_detect():
    """Calling set_default_environment(None) forces next render to re-detect root."""
    # Set an explicit environment first
    custom_root = os.path.join(os.getcwd(), "tests")
    custom_env = Environment(loader=FileSystemLoader(custom_root))
    Renderer.set_default_environment(custom_env)
    assert Renderer.peek_default_environment() is custom_env

    # Reset to None
    Renderer.set_default_environment(None)
    assert Renderer.peek_default_environment() is None

    # Next get_default_environment should re-detect and create new env
    new_env = Renderer.get_default_environment()
    assert new_env is not custom_env
    assert isinstance(new_env.loader, FileSystemLoader)


def test_set_default_environment_with_path_creates_autoescape_env():
    """set_default_environment(path) creates env with FileSystemLoader and autoescape=True."""
    custom_root = os.path.join(os.getcwd(), "tests")
    Renderer.set_default_environment(custom_root)

    env = Renderer.get_default_environment()
    assert isinstance(env.loader, FileSystemLoader)
    assert env.loader.searchpath[0] == custom_root
    assert env.autoescape is True


def test_caller_supplied_environment_used_as_is():
    """A custom Environment is used directly (caller responsible for autoescape)."""
    custom_root = os.path.join(os.getcwd(), "tests")
    # Caller creates environment with autoescape=False
    custom_env = Environment(
        loader=FileSystemLoader(custom_root),
        autoescape=False,
    )
    Renderer.set_default_environment(custom_env)

    # That exact environment is returned, autoescape setting unchanged
    assert Renderer.get_default_environment() is custom_env
    assert Renderer.get_default_environment().autoescape is False


def test_cached_renderers_cleared_on_env_change():
    """Cached Renderer instances cleared when environment changes."""
    Renderer.set_default_environment(None)

    # Get first renderer
    renderer_1 = Renderer.get_default_renderer()
    renderer_1_id = id(renderer_1)

    # Cache should not be empty
    assert len(Renderer._default_renderers) > 0

    # Set new environment
    new_root = os.path.join(os.getcwd(), "tests")
    Renderer.set_default_environment(new_root)

    # Cache should be cleared
    assert len(Renderer._default_renderers) == 0

    # Next get_default_renderer returns a different instance
    renderer_2 = Renderer.get_default_renderer()
    renderer_2_id = id(renderer_2)
    assert renderer_1_id != renderer_2_id


def test_autoescape_escapes_text_content():
    """Text interpolation is HTML-escaped ({{ unsafe }} produces &lt;tag&gt;)."""
    Renderer.set_default_environment(None)
    renderer = Renderer.get_default_renderer()
    env = renderer.environment

    # Template with unsafe text
    template = env.from_string('<p>{{ content }}</p>')
    result = template.render(content='<script>alert(1)</script>')

    assert '&lt;script&gt;' in result
    assert '<script>' not in result


def test_autoescape_escapes_attributes():
    """Attribute interpolation is HTML-escaped."""
    Renderer.set_default_environment(None)
    renderer = Renderer.get_default_renderer()
    env = renderer.environment

    # Template with unsafe attribute
    template = env.from_string('<div class="{{ attr }}"></div>')
    result = template.render(attr='x" onload="alert(1)')

    # Quote can be escaped as &quot; or &#34;; both are valid
    assert ('&quot;' in result or '&#34;' in result)
    # Verify the quote is escaped so the attribute can't break out
    assert 'onload="alert' not in result


def test_non_filesystem_loader_raises_error():
    """Non-FileSystemLoader raises ValueError."""
    # Create environment with DictLoader (not FileSystemLoader)
    dict_env = Environment(loader=DictLoader({'test.html': '<p>test</p>'}))

    with pytest.raises(ValueError, match="Jinja2 loader must be a FileSystemLoader"):
        get_loader_root(dict_env)


def test_missing_template_raises_error():
    """Missing template raises TemplateNotFound."""
    Renderer.set_default_environment(None)
    env = Renderer.get_default_environment()

    with pytest.raises(TemplateNotFound):
        env.get_template('nonexistent_template_xyz.pjx')

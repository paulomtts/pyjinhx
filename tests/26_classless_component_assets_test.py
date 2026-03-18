"""
Tests for CSS/JS asset collection from classless (template-only) components.

Prior to the fix, _collect_component_javascript/_css resolved the asset directory
via Finder.get_class_directory(BaseComponent), which pointed to the pyjinhx package
directory rather than the user's component directory.  Assets were never found.

The fix: when the component is a bare BaseComponent fallback, derive the asset
directory and filename stem from the template path instead.
"""
import os
import tempfile

from jinja2 import Environment, FileSystemLoader

from pyjinhx import Registry
from pyjinhx.renderer import Renderer


def test_classless_component_js_collected():
    """JS co-located with a template-only component is collected and injected."""
    Registry.clear_instances()

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "toast_alert.html"), "w") as f:
            f.write('<div id="{{ id }}" class="toast">{{ content }}</div>\n')
        with open(os.path.join(temp_dir, "toast-alert.js"), "w") as f:
            f.write("console.log('toast loaded');")

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        rendered = renderer.render('<ToastAlert id="t1">Hello</ToastAlert>')

        assert "console.log('toast loaded');" in rendered
        assert '<div id="t1" class="toast">Hello</div>' in rendered


def test_classless_component_css_collected():
    """CSS co-located with a template-only component is collected and injected."""
    Registry.clear_instances()

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "info_badge.html"), "w") as f:
            f.write('<span id="{{ id }}" class="badge">{{ content }}</span>\n')
        with open(os.path.join(temp_dir, "info-badge.css"), "w") as f:
            f.write(".badge { color: blue; }")

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        rendered = renderer.render('<InfoBadge id="b1">Info</InfoBadge>')

        assert ".badge { color: blue; }" in rendered
        assert '<span id="b1" class="badge">Info</span>' in rendered


def test_classless_component_both_assets_collected():
    """Both JS and CSS are collected from a template-only component."""
    Registry.clear_instances()

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "drop_down.html"), "w") as f:
            f.write('<div id="{{ id }}">{{ content }}</div>\n')
        with open(os.path.join(temp_dir, "drop-down.js"), "w") as f:
            f.write("console.log('dropdown loaded');")
        with open(os.path.join(temp_dir, "drop-down.css"), "w") as f:
            f.write(".dropdown { display: none; }")

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        rendered = renderer.render('<DropDown id="d1">Options</DropDown>')

        assert "console.log('dropdown loaded');" in rendered
        assert ".dropdown { display: none; }" in rendered


def test_classless_component_js_deduplicated():
    """JS from the same classless component is not injected twice."""
    Registry.clear_instances()

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "tag_chip.html"), "w") as f:
            f.write('<span id="{{ id }}">{{ content }}</span>\n')
        with open(os.path.join(temp_dir, "tag-chip.js"), "w") as f:
            f.write("console.log('chip loaded');")

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        rendered = renderer.render(
            '<TagChip id="c1">One</TagChip><TagChip id="c2">Two</TagChip>'
        )

        assert rendered.count("console.log('chip loaded');") == 1


def test_classless_component_css_injected_before_html():
    """CSS from a classless component is injected before the HTML markup."""
    Registry.clear_instances()

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "nav_bar.html"), "w") as f:
            f.write('<nav id="{{ id }}">{{ content }}</nav>\n')
        with open(os.path.join(temp_dir, "nav-bar.css"), "w") as f:
            f.write("nav { background: black; }")

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        rendered = renderer.render('<NavBar id="nav1">Menu</NavBar>')

        style_pos = rendered.find("<style>")
        nav_pos = rendered.find("<nav")
        assert style_pos != -1
        assert style_pos < nav_pos, "CSS <style> block should precede the HTML"


def test_classless_component_js_injected_after_html():
    """JS from a classless component is injected after the HTML markup."""
    Registry.clear_instances()

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "side_bar.html"), "w") as f:
            f.write('<aside id="{{ id }}">{{ content }}</aside>\n')
        with open(os.path.join(temp_dir, "side-bar.js"), "w") as f:
            f.write("console.log('sidebar loaded');")

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        rendered = renderer.render('<SideBar id="s1">Links</SideBar>')

        aside_pos = rendered.find("<aside")
        script_pos = rendered.find("<script>")
        assert script_pos != -1
        assert aside_pos < script_pos, "JS <script> block should follow the HTML"


def test_classless_component_no_assets_no_injection():
    """A template-only component with no co-located assets injects nothing extra."""
    Registry.clear_instances()

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "plain_text.html"), "w") as f:
            f.write('<p id="{{ id }}">{{ content }}</p>\n')

        env = Environment(loader=FileSystemLoader(temp_dir))
        renderer = Renderer(env, auto_id=True)

        rendered = renderer.render('<PlainText id="p1">Words</PlainText>')

        assert "<script>" not in rendered
        assert "<style>" not in rendered
        assert '<p id="p1">Words</p>' in rendered

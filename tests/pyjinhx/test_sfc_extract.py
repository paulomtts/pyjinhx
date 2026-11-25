"""Tests for reading a component's inline template out of its module source."""

import textwrap

import jinja2
import pytest

from pyjinhx.sfc import extract_template

BADGE = textwrap.dedent('''\
    from pyjinhx import BaseComponent


    class Badge(BaseComponent):
        label: str

        template = """
        <span class="badge">
          {{ label }}
        </span>
        """
    ''')


def render(source: str, **context: object) -> str:
    return jinja2.Environment().from_string(source).render(**context)


def test_the_template_renders_without_its_indentation_or_blank_edges():
    template = extract_template(BADGE, "Badge")
    assert render(template, label="new") == '<span class="badge">\n  new\n</span>'


def test_each_template_line_keeps_its_line_number_from_the_module():
    template = extract_template(BADGE, "Badge")
    module_lines = BADGE.splitlines()
    template_lines = template.splitlines()
    assert module_lines[8].strip() == "{{ label }}"
    assert template_lines[8].strip() == "{{ label }}"


def test_a_template_starting_on_the_opening_quote_line_is_aligned_too():
    source = 'class Tag:\n    x = 1\n    template = """<b>\n{{ label }}</b>"""\n'
    template = extract_template(source, "Tag")
    assert template.splitlines()[3] == "{{ label }}</b>"
    assert render(template, label="hi") == "<b>\nhi</b>"


def test_the_class_is_picked_by_name_when_a_module_holds_several():
    source = textwrap.dedent('''\
        class First:
            template = "<i>first</i>"


        class Second:
            template = "<i>second</i>"
        ''')
    assert render(extract_template(source, "Second")) == "<i>second</i>"


def test_a_raw_string_keeps_its_backslashes():
    source = 'class Tag:\n    template = r"<script>/\\d+/</script>"\n'
    assert render(extract_template(source, "Tag")) == r"<script>/\d+/</script>"


def test_a_class_without_a_template_is_an_error_naming_the_class():
    with pytest.raises(ValueError, match="Badge.*no inline template"):
        extract_template("class Badge:\n    label = 1\n", "Badge")


def test_a_computed_template_is_an_error_pointing_at_its_line():
    source = 'class Tag:\n    name = "b"\n    template = f"<{name}/>"\n'
    with pytest.raises(ValueError, match="line 3.*plain string literal"):
        extract_template(source, "Tag")

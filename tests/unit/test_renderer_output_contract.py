"""The renderer's output contract: Markup objects, escaped by default."""
import importlib.util
import os
import sys
import tempfile

from markupsafe import Markup

from pyjinhx.renderer import Renderer


def test_render_returns_markup():
    """render() and __html__() both return a markupsafe.Markup instance.

    Uses the tmp-template + importlib pattern from tests/unit/test_jinja_template_auto_lookup.py so the component
    class lives in a real file and inspect.getfile() succeeds.
    """
    original_environment = Renderer.peek_default_environment()

    with tempfile.TemporaryDirectory() as temp_dir:
        module_path = os.path.join(temp_dir, "output_probe.py")
        with open(module_path, "w", encoding="utf-8") as fh:
            fh.write(
                "from pyjinhx import BaseComponent\n\n"
                "class OutputProbe(BaseComponent):\n"
                "    body: str = ''\n"
            )

        template_path = os.path.join(temp_dir, "output_probe.html")
        with open(template_path, "w", encoding="utf-8") as fh:
            fh.write('<div id="{{ id }}">{{ body }}</div>\n')

        Renderer.set_default_environment(temp_dir)

        spec = importlib.util.spec_from_file_location("output_probe", module_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["output_probe"] = module
        spec.loader.exec_module(module)

        OutputProbe = getattr(module, "OutputProbe")
        component = OutputProbe(id="out-1", body="hello")
        render_result = component.render()
        html_result = component.__html__()

    Renderer.set_default_environment(original_environment)
    sys.modules.pop("output_probe", None)

    assert isinstance(render_result, Markup), (
        f"render() must return markupsafe.Markup, got {type(render_result)}"
    )
    assert isinstance(html_result, Markup), (
        f"__html__() must return markupsafe.Markup, got {type(html_result)}"
    )


def test_renderer_escapes_scalar_values_by_default():
    """A scalar (non-slot) field containing literal HTML tags is escaped.

    Autoescape is on by default (see renderer.py Environment(autoescape=True)).
    A plain ``str`` field is not a slot, so Jinja escapes its value: ``<em>``
    becomes ``&lt;em&gt;`` in the output. Raw HTML requires a ``Slot`` field,
    ``Markup(...)``, or ``{{ value|safe }}``.
    """
    original_environment = Renderer.peek_default_environment()

    with tempfile.TemporaryDirectory() as temp_dir:
        module_path = os.path.join(temp_dir, "output_probe2.py")
        with open(module_path, "w", encoding="utf-8") as fh:
            fh.write(
                "from pyjinhx import BaseComponent\n\n"
                "class OutputProbe2(BaseComponent):\n"
                "    body: str = ''\n"
            )

        template_path = os.path.join(temp_dir, "output_probe2.html")
        with open(template_path, "w", encoding="utf-8") as fh:
            fh.write('<div id="{{ id }}">{{ body }}</div>\n')

        Renderer.set_default_environment(temp_dir)

        spec = importlib.util.spec_from_file_location("output_probe2", module_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["output_probe2"] = module
        spec.loader.exec_module(module)

        OutputProbe2 = getattr(module, "OutputProbe2")
        component = OutputProbe2(id="out-2", body="<em>hi</em>")
        rendered = str(component.render())

    Renderer.set_default_environment(original_environment)
    sys.modules.pop("output_probe2", None)

    # Autoescape is on: a scalar str field is HTML-escaped.
    assert "&lt;em&gt;hi&lt;/em&gt;" in rendered, (
        "Renderer must HTML-escape scalar values by default"
    )
    assert "<em>hi</em>" not in rendered, (
        "Renderer must not emit raw scalar values — raw HTML needs Slot/Markup/|safe"
    )


def test_renderer_renders_slot_value_raw():
    """A ``Slot``-annotated field renders its string value as raw HTML.

    Even with autoescape on, the context builder wraps slot strings as
    ``Markup`` (see Slot machinery), so literal tags pass through verbatim.
    """
    original_environment = Renderer.peek_default_environment()

    with tempfile.TemporaryDirectory() as temp_dir:
        module_path = os.path.join(temp_dir, "output_probe3.py")
        with open(module_path, "w", encoding="utf-8") as fh:
            fh.write(
                "from pyjinhx import BaseComponent, Slot\n\n"
                "class OutputProbe3(BaseComponent):\n"
                "    body: Slot = ''\n"
            )

        template_path = os.path.join(temp_dir, "output_probe3.html")
        with open(template_path, "w", encoding="utf-8") as fh:
            fh.write('<div id="{{ id }}">{{ body }}</div>\n')

        Renderer.set_default_environment(temp_dir)

        spec = importlib.util.spec_from_file_location("output_probe3", module_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["output_probe3"] = module
        spec.loader.exec_module(module)

        OutputProbe3 = getattr(module, "OutputProbe3")
        component = OutputProbe3(id="out-3", body="<em>hi</em>")
        rendered = str(component.render())

    Renderer.set_default_environment(original_environment)
    sys.modules.pop("output_probe3", None)

    # Slot field: literal tags are preserved unescaped.
    assert "<em>hi</em>" in rendered, (
        "Slot field should render its string value as raw HTML"
    )
    assert "&lt;em&gt;" not in rendered, (
        "Slot field must not HTML-escape its value"
    )

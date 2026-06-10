"""The renderer's output contract: Markup objects, unescaped by design."""
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


def test_renderer_unescapes_final_markup():
    """body containing literal HTML tags renders them unescaped.

    The renderer calls Markup(Markup(rendered_markup).unescape()) on the
    final output (see renderer.py render_component_with_context). This is
    load-bearing: attribute safety must be enforced at construction time,
    not by escaping. Jinja's default autoescape is off so the template
    renders body verbatim; the outer Markup() wraps it as safe markup.
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

    # Jinja2 default environment has autoescape=False, so <em>hi</em> passes
    # through verbatim; the outer Markup() preserves the literal tags.
    assert "<em>hi</em>" in rendered, (
        "Renderer should preserve literal tags — '<em>hi</em>' expected in output"
    )
    assert "&lt;em&gt;" not in rendered, (
        "Renderer must not HTML-escape the final output string"
    )

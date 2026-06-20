from pyjinhx import BaseComponent


def test_inline_template_is_rendered():
    class InlineWidget(BaseComponent):
        label: str

    InlineWidget._pjx_inline_template = '<span class="w">{{ label }}</span>'
    html = InlineWidget(label="hello").render()
    assert "<span" in html
    assert "hello" in html


def test_inline_template_none_by_default():
    class InlinePlain(BaseComponent):
        pass

    assert InlinePlain._pjx_inline_template is None
    assert InlinePlain._pjx_source_path is None


def test_source_path_classvar_exists():
    class InlineMyComp(BaseComponent):
        pass

    InlineMyComp._pjx_source_path = "/some/path/MyComp.pjx"
    assert InlineMyComp._pjx_source_path == "/some/path/MyComp.pjx"

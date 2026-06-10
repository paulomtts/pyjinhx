from typing import ClassVar

from pyjinhx import ReactiveComponent


class AutoIdWidget(ReactiveComponent):
    value: int = 0
    reacts_to: ClassVar[set[str]] = {"things"}

    @classmethod
    def load(cls) -> "AutoIdWidget":
        return cls(value=1)


def test_id_defaults_to_kebab_class_name():
    assert AutoIdWidget().id == "auto-id-widget"


def test_load_without_explicit_id_uses_default():
    assert AutoIdWidget.load().id == "auto-id-widget"


def test_explicit_id_overrides_default():
    assert AutoIdWidget(id="custom").id == "custom"


def test_default_id_is_stamped_as_data_pjx_id():
    html = str(AutoIdWidget()._render(source="<span>{{ value }}</span>"))
    assert 'data-pjx-id="auto-id-widget"' in html
    assert 'data-pjx-type="AutoIdWidget"' in html

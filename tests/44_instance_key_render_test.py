from typing import ClassVar

from pyjinhx import ReactiveComponent
from pyjinhx.utils import read_client_runtime


class KeyedCard(ReactiveComponent):
    title: str = ""
    reacts_to: ClassVar[set[str]] = {"card:{key}"}

    @classmethod
    def load(cls, key) -> "KeyedCard":
        return cls(title=f"card {key}")


def test_keyed_root_is_stamped_with_data_pjx_key():
    html = str(KeyedCard.load("7")._render(source="<div>{{ title }}</div>"))
    assert 'data-pjx-id="keyed-card-7"' in html
    assert 'data-pjx-key="7"' in html
    assert 'data-pjx-type="KeyedCard"' in html


def test_key_is_available_in_template_context():
    html = str(
        KeyedCard.load("7")._render(source="<a href='/cards/{{ key }}'>{{ title }}</a>")
    )
    assert "/cards/7" in html


def test_runtime_reports_key_in_manifest():
    src = read_client_runtime()
    assert "data-pjx-key" in src or "pjxKey" in src
    assert "key:" in src

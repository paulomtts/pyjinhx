from typing import Annotated, ClassVar

from pyjinhx import PjxLoad, ReactiveComponent
from pyjinhx.utils import read_client_runtime


class KeyedCard(ReactiveComponent):
    card_key: Annotated[str, PjxLoad()]
    title: str = ""
    reacts_to: ClassVar[set[str]] = {"card"}

    @classmethod
    def load(cls, key: str | int) -> "KeyedCard":
        return cls(card_key=str(key), title=f"card {key}")


def test_keyed_root_is_stamped_with_data_pjx_load():
    html = str(KeyedCard.load("7")._render(source="<div>{{ title }}</div>"))
    assert 'data-pjx-id="keyed-card-7"' in html
    assert 'data-pjx-load="7"' in html
    assert 'data-pjx-type="KeyedCard"' in html


def test_pjx_load_field_is_available_in_template_context():
    html = str(
        KeyedCard.load("7")._render(
            source="<a href='/cards/{{ card_key }}'>{{ title }}</a>"
        )
    )
    assert "/cards/7" in html


def test_runtime_reports_load_in_manifest():
    src = read_client_runtime()
    assert "data-pjx-load" in src or "pjxLoad" in src
    assert "load:" in src or "entry.load" in src

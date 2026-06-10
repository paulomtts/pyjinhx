from typing import ClassVar

from pyjinhx import ReactiveComponent
from tests.ui.unified_component import UnifiedComponent


class StampCounter(ReactiveComponent):
    remaining: int = 0
    reacts_to: ClassVar[set[str]] = {"todos"}

    @classmethod
    def load(cls) -> "StampCounter":
        return cls(id="stamp-counter", remaining=0)


def test_reactive_root_is_stamped():
    counter = StampCounter(id="c1", remaining=3)
    html = str(counter._render(source="<span class='c'>{{ remaining }} left</span>"))
    assert html.startswith("<span class='c' data-pjx-id=\"c1\"")
    assert 'data-pjx-type="StampCounter"' in html
    assert f'data-pjx-hash="{counter.state_hash()}"' in html
    assert ">3 left</span>" in html


def test_non_reactive_component_is_not_stamped():
    html = str(UnifiedComponent(id="u1", text="hi")._render())
    assert "data-pjx-id" not in html
    assert "data-pjx-type" not in html

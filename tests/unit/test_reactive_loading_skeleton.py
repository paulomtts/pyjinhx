from pyjinhx import MutationKey, ReactiveComponent
from pyjinhx.utils import read_client_runtime


class Keys(MutationKey):
    TODOS = "todos"


class LoadingProbe(ReactiveComponent, react={Keys.TODOS}):
    value: int = 0

    @classmethod
    def load(cls) -> "LoadingProbe":
        return cls(id="probe", value=0)


def test_loading_authored_on_root_is_preserved():
    html = str(
        LoadingProbe(id="p", value=2)._render(
            source='<span data-pjx-loading="skeleton">{{ value }}</span>'
        )
    )
    assert 'data-pjx-loading="skeleton"' in html
    assert 'data-pjx-reacts="todos"' in html
    # stamping must not duplicate the author's attribute
    assert html.count('data-pjx-loading="') == 1


def test_loading_authored_on_inner_element_is_preserved():
    html = str(
        LoadingProbe(id="p", value=2)._render(
            source='<div><button data-pjx-loading="spinner">x</button></div>'
        )
    )
    assert 'data-pjx-loading="spinner"' in html
    assert 'data-pjx-reacts="todos"' in html  # reactivity stays on the root <div>


def test_no_loading_attribute_when_template_omits_it():
    html = str(LoadingProbe(id="p", value=2)._render(source="<span>{{ value }}</span>"))
    assert 'data-pjx-reacts="todos"' in html
    assert "data-pjx-loading" not in html


def test_runtime_has_loading_indicator_logic():
    source = read_client_runtime()
    assert "htmx:beforeRequest" in source
    assert "htmx:afterSettle" in source
    assert "loadend" in source
    assert "data-pjx-loading" in source
    assert "data-pjx-loading-extra" in source
    assert "data-pjx-reacts" in source
    assert "triggerLoad" in source
    assert "pjx-loading--skeleton" in source
    assert "pjx-loading--spinner" in source
    assert "pjx-spin" in source
    # overridable style tokens
    assert "--pjx-spinner-color" in source
    assert "--pjx-skeleton-color" in source

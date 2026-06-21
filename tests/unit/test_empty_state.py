"""Unit tests for the refactored PJXEmptyState (content-slot API)."""
from pyjinhx.builtins import PJXEmptyState


# --- New content-slot API ---

def test_empty_state_renders_root_div():
    html = str(PJXEmptyState(id="es-root").render())
    assert 'class="pjx-empty-state"' in html
    assert 'id="es-root"' in html


def test_empty_state_content_renders_inside_root():
    html = str(PJXEmptyState(id="es-content", content="<h3>No results</h3>").render())
    assert "<h3>No results</h3>" in html
    assert 'class="pjx-empty-state"' in html


def test_empty_state_empty_content_renders_clean_div():
    html = str(PJXEmptyState(id="es-empty").render())
    assert 'class="pjx-empty-state"' in html
    # No extra divs for old presentational elements
    assert "pjx-empty-state__title" not in html
    assert "pjx-empty-state__desc" not in html
    assert "pjx-empty-state__image" not in html
    assert "pjx-empty-state__action" not in html
    assert "pjx-empty-state__actions" not in html


def test_empty_state_class_name_appends():
    html = str(PJXEmptyState(id="es-cn", class_name="my-class").render())
    assert "pjx-empty-state my-class" in html


def test_empty_state_removed_fields_not_in_model_fields():
    """Removed presentational fields must not exist on the model."""
    removed = {"image", "title", "description", "action", "actions"}
    actual = set(PJXEmptyState.model_fields.keys())
    assert removed.isdisjoint(actual), (
        f"Expected fields {removed & actual} to be removed from PJXEmptyState"
    )


def test_empty_state_new_fields_present():
    fields = set(PJXEmptyState.model_fields.keys())
    assert "content" in fields
    assert "suggestions" in fields
    assert "class_name" in fields


# --- Suggestion chips (preserved behavior, issue #77) ---

def test_empty_state_suggestions_renders_chips():
    html = str(
        PJXEmptyState(
            id="es-chips",
            suggestions=[
                {"label": "Draft a message"},
                {"label": "Summarise a thread"},
            ],
        ).render()
    )
    assert '<div class="pjx-empty-state__suggestions">' in html
    assert "Draft a message" in html
    assert "Summarise a thread" in html
    assert 'class="pjx-empty-state__chip"' in html


def test_empty_state_chip_default_event_and_value():
    html = str(
        PJXEmptyState(
            id="es-chip-defaults",
            suggestions=[{"label": "Fill me in"}],
        ).render()
    )
    assert 'data-pjx-suggestion="Fill me in"' in html
    assert "@click=" in html
    assert "pjx:suggestion" in html


def test_empty_state_chip_custom_event_and_value():
    html = str(
        PJXEmptyState(
            id="es-chip-custom",
            suggestions=[{"label": "Click me", "value": "fill-input-value", "event": "fill-input"}],
        ).render()
    )
    assert 'data-pjx-suggestion="fill-input-value"' in html
    assert "fill-input" in html
    assert "Click me" in html


def test_empty_state_no_suggestions_block_when_empty():
    html = str(PJXEmptyState(id="es-no-chips").render())
    assert 'class="pjx-empty-state__suggestions"' not in html


def test_empty_state_chip_event_is_not_interpolated_into_click_handler():
    # Security regression: the event name must never be interpolated into the
    # @click JS string literal. It is carried in a data attribute and read via
    # $el.dataset, so a quote in the event name cannot break out and inject JS.
    payload = "x');alert(1);('"
    html = str(
        PJXEmptyState(
            id="es-xss",
            suggestions=[{"label": "x", "event": payload}],
        ).render()
    )
    assert (
        '@click="$dispatch($el.dataset.pjxEvent, { value: $el.dataset.pjxSuggestion })"'
        in html
    )
    assert "$dispatch('" not in html

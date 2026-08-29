"""The todo example's templates: each one renders, with its htmx wiring intact."""

from examples.todo import store as todo_store
from examples.todo.components import (
    App,
    ClearButton,
    Counter,
    ItemList,
    ItemRow,
    Total,
)
from pyjinhx.rendering import render


def _app():
    """The whole tree, assembled the way the route does it — tags do the loading."""
    return App(id="app")


class TestItemRow:
    def test_renders_title_and_toggle_wiring(self, scope):
        todo = todo_store.all_todos()[0]
        row = ItemRow.load(todo.id)
        row.id = f"row-{todo.id}"

        html = render(row, scope)

        assert "Write the docs" in html
        assert f'hx-post="/rows/{todo.id}/toggle"' in html
        assert 'hx-target="closest [data-pjx-id]"' in html

    def test_keeps_the_skeleton_loading_indicator(self, scope):
        todo = todo_store.all_todos()[0]
        row = ItemRow.load(todo.id)
        row.id = f"row-{todo.id}"

        assert 'data-pjx-loading="skeleton"' in render(row, scope)

    def test_done_row_gets_the_done_class(self, scope):
        todo = todo_store.all_todos()[0]
        todo_store.toggle(todo.id)
        row = ItemRow.load(todo.id)
        row.id = f"row-{todo.id}"

        assert 'class="todo done"' in render(row, scope)


class TestItemList:
    def test_renders_every_row(self, scope):
        item_list = ItemList.load()
        item_list.id = "list"

        html = render(item_list, scope)

        assert html.count('data-pjx-loading="skeleton"') == 3
        assert 'id="list"' in html

    def test_empty_list_renders_an_empty_ul(self, scope):
        for todo in list(todo_store.all_todos()):
            todo_store.toggle(todo.id)
        todo_store.clear_completed()
        item_list = ItemList.load()
        item_list.id = "list"

        html = render(item_list, scope)

        assert "<li" not in html
        assert "<ul" in html


class TestStatusComponents:
    def test_counter_renders_its_count(self, scope):
        counter = Counter.load()
        counter.id = "counter"

        assert "3 left" in render(counter, scope)

    def test_total_renders_its_count(self, scope):
        total = Total.load()
        total.id = "total"

        assert "3 total" in render(total, scope)

    def test_clear_button_keeps_its_loading_indicator_attrs(self, scope):
        button = ClearButton.load()
        button.id = "clear"

        html = render(button, scope)

        assert 'data-pjx-loading="spinner"' in html
        assert 'data-pjx-loading-extra=".todo.done"' in html
        assert 'hx-post="/todos/clear-completed"' in html

    def test_clear_button_is_disabled_with_nothing_completed(self, scope):
        button = ClearButton.load()
        button.id = "clear"

        assert "disabled" in render(button, scope)


class TestApp:
    def test_renders_the_whole_tree(self, scope):
        html = render(_app(), scope)

        assert "Write the docs" in html
        assert "3 left" in html
        assert "3 total" in html
        assert "Clear completed (0)" in html

    def test_renders_the_composer_form(self, scope):
        html = render(_app(), scope)

        assert 'hx-post="/todos"' in html
        assert 'name="text"' in html

    def test_children_render_id_stamped_from_their_tags(self, scope):
        from pyjinhx.reactive.root_attrs import stamp_reactive_root_attrs

        scope.on_rendered.append(stamp_reactive_root_attrs)
        html = render(_app(), scope)

        assert 'data-pjx-id="counter"' in html
        assert 'data-pjx-id="total"' in html
        assert 'data-pjx-id="clear"' in html
        assert 'data-pjx-id="list"' in html


class TestDesignSystem:
    def test_app_output_inlines_the_stylesheet(self, scope):
        html = render(_app(), scope)

        assert "<style" in html
        assert "--accent" in html

    def test_the_palette_is_the_pastel_one(self, scope):
        html = render(_app(), scope)

        assert "#faf9f7" in html
        assert "#b9a6f2" in html
        # The v0.x neon-terminal accent is gone, not merely overridden.
        assert "#b8ff4d" not in html

    def test_no_external_font_or_cdn_dependency(self, scope):
        html = render(_app(), scope)

        assert "fonts.googleapis.com" not in html
        assert "fonts.gstatic.com" not in html
        assert "@import" not in html
        assert "<link" not in html
        assert "IBM Plex Mono" not in html

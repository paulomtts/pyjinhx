"""Keys for the todo example are real MutationKey members."""

from pyjinhx import MutationKey, mutates

from examples.todo.keys import Keys


def test_keys_subclasses_mutation_key():
    assert issubclass(Keys, MutationKey)


def test_keys_have_the_documented_members():
    assert Keys.TODOS.value == "todos"
    assert Keys.TODO_LIST.value == "todo-list"


def test_keys_are_accepted_by_mutates_without_raising():
    @mutates(Keys.TODOS, Keys.TODO_LIST)
    def op() -> str:
        return "done"

    assert op.__name__ == "op"

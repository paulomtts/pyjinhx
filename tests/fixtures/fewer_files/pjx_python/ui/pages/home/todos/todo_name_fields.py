from tests.fixtures.fewer_files.pjx_python.ui.base_primitives.name_field.name_field import (
    NameField,
)


class TaskNameField(NameField):
    input_id: str = "task-name"
    label: str = "New task"

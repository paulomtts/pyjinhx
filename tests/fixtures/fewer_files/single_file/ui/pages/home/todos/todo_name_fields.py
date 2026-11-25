from tests.fixtures.fewer_files.single_file.ui.base_primitives.name_field.name_field import (
    NameField,
)


class ProjectNameField(NameField):
    input_id: str = "project-name"
    label: str = "Project"


class TaskNameField(NameField):
    input_id: str = "task-name"
    label: str = "New task"

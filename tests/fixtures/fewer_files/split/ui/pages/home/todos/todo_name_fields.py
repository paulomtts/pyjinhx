from tests.fixtures.fewer_files.split.ui.base_primitives.name_field.name_field import (
    NameField,
)


class ProjectNameField(NameField):
    input_id: str = "project-name"
    label: str = "Project"


class TaskNameField(NameField):
    input_id: str = "task-name"
    label: str = "New task"


class TeamNameField(NameField):
    input_id: str = "team-name"
    label: str = "Team"


class OwnerNameField(NameField):
    input_id: str = "owner-name"
    label: str = "Owner"


class ListNameField(NameField):
    input_id: str = "list-name"
    label: str = "List"


class TagNameField(NameField):
    input_id: str = "tag-name"
    label: str = "Tag"


class LabelNameField(NameField):
    input_id: str = "label-name"
    label: str = "Label"

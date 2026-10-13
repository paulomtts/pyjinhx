from pydantic import BaseModel, ConfigDict, Field

from pyjinhx._component import Slot


class PJXRosterItem(BaseModel):
    """One roster entry, shown as a chip or a result row: its posted value, label and visuals."""

    model_config = ConfigDict(frozen=True)

    value: str = Field(min_length=1)
    label: str = Field(min_length=1)
    subtitle: str = ""
    initials: str = ""
    color: str = ""
    src: str = ""
    icon: str = ""
    extra: Slot = ""
    detail: Slot = ""

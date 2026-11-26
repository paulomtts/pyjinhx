"""Names for ``{#def#}`` header tests to reach by dotted import path."""

import enum

PAGE_SIZE = 25


class Tone(enum.Enum):
    INFO = "info"
    WARN = "warn"


def make_tags() -> list[str]:
    return ["new"]

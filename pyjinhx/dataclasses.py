from dataclasses import dataclass, field

@dataclass
class Tag:
    name: str
    attrs: dict[str, str]
    children: list["Tag | str"] = field(default_factory=list)
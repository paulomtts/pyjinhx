from pydantic import computed_field, field_validator

from pyjinhx import BaseComponent
from tests.fixtures.fewer_files.domain import Todo, format_cents, normalise_currency


class Money(BaseComponent):
    """An amount in cents, shown in its currency."""

    cents: int
    currency: str = "EUR"

    @field_validator("currency")
    @classmethod
    def _known_currency(cls, value: str) -> str:
        return normalise_currency(value)

    @computed_field
    @property
    def amount(self) -> str:
        return format_cents(self.cents, self.currency)

    @property
    def is_free(self) -> bool:
        return self.cents == 0

    @classmethod
    def of(cls, todo: Todo) -> "Money":
        return cls(cents=todo.cents)

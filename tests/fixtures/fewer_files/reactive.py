"""The app's own reactive base, shared by every shape that has classes."""

import re
from typing import Any

from pydantic import ModelWrapValidatorHandler, model_validator

from pyjinhx import ReactiveComponent

_WORD_START = re.compile(r"(?<!^)(?=[A-Z])")


class AppReactive(ReactiveComponent):
    """A reactive component whose id defaults to its kebab-cased class name.

    A one-per-page region keeps the same DOM id across re-renders, so swap
    targets and stylesheet hooks written against it keep matching.
    """

    @model_validator(mode="wrap")
    @classmethod
    def _id_from_type(cls, data: Any, handler: ModelWrapValidatorHandler[Any]) -> Any:
        if isinstance(data, dict) and not data.get("id"):
            data = {**data, "id": _WORD_START.sub("-", cls.__name__).lower()}
        return handler(data)

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]


class PJXChartSeries(BaseModel):
    """One named row of chart data: a value per label, ``None`` where it is missing."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    values: list[FiniteFloat | None]

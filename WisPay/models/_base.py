from __future__ import annotations

from datetime import datetime
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints


def _require_aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone")
    return value


type AwareDateTime = Annotated[datetime, AfterValidator(_require_aware_datetime)]
type NonEmptyStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]
type Sha256Digest = Annotated[
    str,
    StringConstraints(pattern=r"^[0-9a-f]{64}$"),
]


class WisPayBaseModel(BaseModel):
    """Immutable base for WisPay domain records and value objects."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
    )

    def evolve(self, **changes: object) -> Self:
        """Return a fully revalidated copy with the supplied field changes."""

        values = self.model_dump(round_trip=True)
        values.update(changes)
        return type(self).model_validate(values)

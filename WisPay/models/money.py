from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import Field, field_validator, model_validator

from ._base import NonEmptyStr, WisPayBaseModel


class Money(WisPayBaseModel):
    """A monetary value with its currency and historical decimal scale."""

    amount: Decimal = Field(ge=Decimal("0"), allow_inf_nan=False)
    currency_code: NonEmptyStr
    decimal_scale: int = Field(ge=0, le=6)

    @field_validator("amount", mode="before")
    @classmethod
    def reject_float_amount(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("money amounts must not use floating-point values")
        return value

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str) -> str:
        normalized = value.upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency code must be a three-letter ISO 4217 code")
        return normalized

    @model_validator(mode="after")
    def validate_decimal_scale(self) -> Self:
        if self.currency_code == "VND" and self.decimal_scale != 0:
            raise ValueError("VND monetary values must use decimal scale 0")

        if self.amount.quantize(self.quantum) != self.amount:
            raise ValueError("amount has more fractional digits than decimal_scale permits")
        return self

    @property
    def quantum(self) -> Decimal:
        return Decimal(1).scaleb(-self.decimal_scale)

    def __add__(self, other: Money) -> Money:
        self._require_compatible(other)
        return Money(
            amount=self.amount + other.amount,
            currency_code=self.currency_code,
            decimal_scale=self.decimal_scale,
        )

    def __sub__(self, other: Money) -> Money:
        self._require_compatible(other)
        result = self.amount - other.amount
        if result < 0:
            raise ValueError("money subtraction cannot produce a negative value")
        return Money(
            amount=result,
            currency_code=self.currency_code,
            decimal_scale=self.decimal_scale,
        )

    def _require_compatible(self, other: Money) -> None:
        if self.currency_code != other.currency_code or self.decimal_scale != other.decimal_scale:
            raise ValueError("money values must have the same currency and decimal scale")

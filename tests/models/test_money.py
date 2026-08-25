from decimal import Decimal

import pytest
from pydantic import ValidationError

from WisPay.models import Money


def test_vnd_money_uses_zero_decimal_scale() -> None:
    value = Money(amount=Decimal("125000"), currency_code="vnd", decimal_scale=0)

    assert value.currency_code == "VND"
    assert value.amount == Decimal("125000")


def test_money_rejects_floats_and_invalid_vnd_scale() -> None:
    with pytest.raises(ValidationError, match="floating-point"):
        Money(amount=12.5, currency_code="USD", decimal_scale=2)

    with pytest.raises(ValidationError, match="VND"):
        Money(amount=Decimal("100"), currency_code="VND", decimal_scale=2)


def test_money_rejects_excess_fractional_digits() -> None:
    with pytest.raises(ValidationError, match="fractional digits"):
        Money(amount=Decimal("1.001"), currency_code="USD", decimal_scale=2)


def test_money_arithmetic_preserves_currency_and_scale() -> None:
    left = Money(amount=Decimal("10.25"), currency_code="USD", decimal_scale=2)
    right = Money(amount=Decimal("2.75"), currency_code="USD", decimal_scale=2)

    assert left + right == Money(
        amount=Decimal("13.00"),
        currency_code="USD",
        decimal_scale=2,
    )
    assert left - right == Money(
        amount=Decimal("7.50"),
        currency_code="USD",
        decimal_scale=2,
    )


def test_money_rejects_incompatible_arithmetic() -> None:
    usd = Money(amount=Decimal("1.00"), currency_code="USD", decimal_scale=2)
    vnd = Money(amount=Decimal("1"), currency_code="VND", decimal_scale=0)

    with pytest.raises(ValueError, match="same currency"):
        _ = usd + vnd

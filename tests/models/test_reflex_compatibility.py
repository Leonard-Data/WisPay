from decimal import Decimal

import reflex as rx
from reflex_base.utils import serializers, types

from WisPay.models import Money


class DomainModelState(rx.State):
    payment_amount: Money = Money(
        amount=Decimal("1000"),
        currency_code="VND",
        decimal_scale=0,
    )

    def replace_amount(self) -> None:
        self.payment_amount = self.payment_amount.evolve(amount=Decimal("2000"))


def test_reflex_accepts_and_serializes_frozen_pydantic_models() -> None:
    assert types.is_valid_var_type(Money)
    assert serializers.has_serializer(Money)
    assert "payment_amount" in DomainModelState.base_vars

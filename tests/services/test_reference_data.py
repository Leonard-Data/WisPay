"""Tests for sample reference data and the provisional document matrix."""

from __future__ import annotations

import pytest

from WisPay.models import DocumentCategory
from WisPay.services.reference_data import (
    COST_CENTERS,
    CURRENCIES,
    EXPENSE_CATEGORIES,
    LEGAL_ENTITIES,
    PAYMENT_METHODS,
    PAYMENT_TERMS,
    POLICY_CATEGORIES,
    REQUESTER_PROTOTYPE,
    RETENTION_POLICY_ID_PROTOTYPE,
    SampleOption,
    doc_requirements,
)


def test_currency_table_forces_vnd_zero_scale() -> None:
    scales = dict(CURRENCIES)
    assert scales["VND"] == 0
    assert scales["USD"] == 2
    assert scales["EUR"] == 2


def test_sample_option_collections_are_non_empty_and_unique() -> None:
    for collection in (
        LEGAL_ENTITIES,
        COST_CENTERS,
        EXPENSE_CATEGORIES,
        PAYMENT_TERMS,
        PAYMENT_METHODS,
    ):
        assert collection
        codes = [option.code for option in collection]
        assert isinstance(collection[0], SampleOption)
        assert len(codes) == len(set(codes))


def test_policy_categories_non_empty() -> None:
    assert len(POLICY_CATEGORIES) >= 3


def test_requester_prototype_is_valid_snapshot() -> None:
    requester = REQUESTER_PROTOTYPE
    assert requester.display_name
    assert "@" in requester.email
    assert requester.captured_at.tzinfo is not None


def test_retention_policy_id_is_fixed_uuid() -> None:
    assert str(RETENTION_POLICY_ID_PROTOTYPE) == "00000000-0000-4000-8000-000000000001"


@pytest.mark.parametrize(
    ("family", "subtype", "required_keys"),
    [
        ("vendor", "standard", {"invoice"}),
        ("employee", "reimbursement", {"receipt"}),
        ("employee", "advance", {"activity_evidence"}),
        ("employee", "settlement", {"expense_statement"}),
        ("employee", "internal", {"policy_approval_evidence"}),
    ],
)
def test_doc_matrix_required_slots(family: str, subtype: str, required_keys: set[str]) -> None:
    requirements = doc_requirements(family, subtype)
    assert {r.key for r in requirements if r.required} == required_keys


def test_vendor_matrix_optional_rows_use_canonical_categories() -> None:
    optional = {r.key: r for r in doc_requirements("vendor", "standard") if not r.required}
    assert set(optional) >= {"purchase_order", "contract", "goods_receipt", "service_acceptance"}
    assert all(isinstance(r.category, DocumentCategory) for r in optional.values())


def test_unknown_combination_returns_empty_checklist() -> None:
    assert doc_requirements("vendor", "reimbursement") == ()
    assert doc_requirements("", "") == ()

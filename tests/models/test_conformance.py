import ast
from pathlib import Path

from pydantic import BaseModel

import WisPay.models as models

CANONICAL_RECORD_NAMES = {
    "PaymentRequest",
    "VendorPaymentDetails",
    "EmployeePaymentDetails",
    "EmployeeAdvanceSettlement",
    "BeneficiaryReference",
    "AccountingDimension",
    "SupportingDocument",
    "EvidenceValidation",
    "Exception",
    "BudgetCheck",
    "ComplianceReview",
    "WorkflowInstance",
    "ApprovalStep",
    "Comment",
    "Notification",
    "PaymentRecord",
    "AuditEvent",
    "RetentionPolicy",
    "UserReference",
    "RoleAssignment",
    "Delegation",
    "PermissionRuleVersion",
}
FORBIDDEN_IMPORT_ROOTS = {"azure", "pyodbc", "reflex", "sqlalchemy", "sqlmodel"}


def model_directory() -> Path:
    package_file = models.__file__
    assert package_file is not None
    return Path(package_file).parent


def test_all_canonical_records_are_exported() -> None:
    exported_names = {model.__name__ for model in models.CANONICAL_RECORD_TYPES}

    assert exported_names == CANONICAL_RECORD_NAMES
    assert set(models.__all__) >= CANONICAL_RECORD_NAMES


def test_canonical_records_are_frozen_pydantic_models() -> None:
    for model_type in models.CANONICAL_RECORD_TYPES:
        assert issubclass(model_type, BaseModel)
        assert model_type.model_config.get("frozen") is True
        assert model_type.model_config.get("extra") == "forbid"
        model_type.model_json_schema()


def test_models_have_no_framework_or_persistence_imports() -> None:
    violations: list[str] = []

    for path in model_directory().glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            imported_root: str | None = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.partition(".")[0]
                    if root in FORBIDDEN_IMPORT_ROOTS:
                        violations.append(f"{path.name}:{node.lineno} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported_root = node.module.partition(".")[0]
            if imported_root in FORBIDDEN_IMPORT_ROOTS:
                violations.append(f"{path.name}:{node.lineno} imports {node.module}")

    assert violations == []


def test_models_do_not_use_dataclasses_float_or_any_annotations() -> None:
    violations: list[str] = []

    for path in model_directory().glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        annotations: list[ast.expr] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) or (
                isinstance(node, ast.arg) and node.annotation is not None
            ):
                annotations.append(node.annotation)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.returns is not None:
                    annotations.append(node.returns)
                if any(
                    isinstance(decorator, ast.Name) and decorator.id == "dataclass"
                    for decorator in node.decorator_list
                ):
                    violations.append(f"{path.name}:{node.lineno} uses dataclass")
            elif isinstance(node, ast.ClassDef) and any(
                isinstance(decorator, ast.Name) and decorator.id == "dataclass"
                for decorator in node.decorator_list
            ):
                violations.append(f"{path.name}:{node.lineno} uses dataclass")

        for annotation in annotations:
            for part in ast.walk(annotation):
                if isinstance(part, ast.Name) and part.id in {"Any", "float"}:
                    violations.append(f"{path.name}:{part.lineno} annotates {part.id}")

    assert violations == []


def test_key_cross_cutting_fields_are_present() -> None:
    assert {"previous_hash", "event_hash"} <= set(models.AuditEvent.model_fields)
    assert {"amount", "currency_code", "decimal_scale"} <= set(models.Money.model_fields)

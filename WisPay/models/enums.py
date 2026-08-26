from enum import StrEnum


class RequestType(StrEnum):
    VENDOR = "Vendor"
    EMPLOYEE = "Employee"


class EmployeeRequestSubtype(StrEnum):
    REIMBURSEMENT = "Reimbursement"
    ADVANCE = "Advance"
    ADVANCE_SETTLEMENT = "Advance Settlement"
    INTERNAL_EXPENDITURE = "Internal Expenditure"


class BeneficiaryType(StrEnum):
    VENDOR = "Vendor"
    EMPLOYEE = "Employee"


class OpexCapexClassification(StrEnum):
    OPEX = "OPEX"
    CAPEX = "CAPEX"


class BudgetResult(StrEnum):
    WITHIN_BUDGET = "Within Budget"
    OVER_BUDGET_EXCEPTION_REQUIRED = "Over Budget — Exception Required"
    NOT_APPLICABLE = "Not Applicable"


class ReviewResult(StrEnum):
    PASSED = "Passed"
    RETURNED = "Returned"
    REJECTED = "Rejected"
    ESCALATED = "Escalated"


class EvidenceValidationResult(StrEnum):
    MATCHED = "Matched"
    NOT_APPLICABLE = "Not Applicable"
    EXCEPTION_ACCEPTED = "Exception Accepted"
    RETURNED = "Returned"
    REJECTED = "Rejected"


class ExceptionSeverity(StrEnum):
    BLOCKING = "Blocking"
    NON_BLOCKING = "Non-blocking"


class ExceptionStatus(StrEnum):
    OPEN = "Open"
    RESOLVED = "Resolved"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"


class DocumentCategory(StrEnum):
    INVOICE = "Invoice"
    CONTRACT = "Contract"
    PURCHASE_ORDER = "Purchase Order"
    RECEIPT = "Receipt"
    GOODS_RECEIPT = "Goods Receipt"
    ACCEPTANCE_RECORD = "Acceptance Record"
    EXPENSE_STATEMENT = "Expense Statement"
    ITINERARY = "Itinerary"
    PAYMENT_PROOF = "Payment Proof"
    OTHER = "Other"


class MalwareScanResult(StrEnum):
    PENDING = "Pending"
    CLEAN = "Clean"
    INFECTED = "Infected"
    FAILED = "Failed"


class AccessClassification(StrEnum):
    INTERNAL = "Internal"
    CONFIDENTIAL = "Confidential"
    RESTRICTED = "Restricted"


class MatchDecisionStatus(StrEnum):
    PROPOSED = "Proposed"
    AUTO_ACCEPTED = "Auto-accepted"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    EXCEPTION = "Exception"


class ApprovalDecision(StrEnum):
    PENDING = "Pending"
    APPROVED = "Approved"
    RETURNED = "Returned"
    REJECTED = "Rejected"
    DELEGATED = "Delegated"


class WorkflowOutcome(StrEnum):
    PENDING = "Pending"
    APPROVED = "Approved"
    RETURNED = "Returned"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"


class NotificationChannel(StrEnum):
    IN_APP = "In-app"
    EMAIL = "Email"


class NotificationStatus(StrEnum):
    PENDING = "Pending"
    SENT = "Sent"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class PaymentReconciliationState(StrEnum):
    PENDING = "Pending"
    RECONCILED = "Reconciled"
    CLOSED = "Closed"


class RoleName(StrEnum):
    REQUESTER = "Requester"
    LINE_MANAGER = "Line Manager"
    BUDGET_OWNER = "Budget Owner"
    FINANCE_REVIEWER = "Finance Reviewer / AP"
    EXECUTIVE_APPROVER = "CFO / Executive Approver"
    PAYMENT_OPERATOR = "Payment Operator"
    SYSTEM_ADMINISTRATOR = "System Administrator"
    AUDITOR = "Auditor / Read-only Reviewer"


class DelegationStatus(StrEnum):
    SCHEDULED = "Scheduled"
    ACTIVE = "Active"
    EXPIRED = "Expired"
    REVOKED = "Revoked"


class CommentVisibility(StrEnum):
    REQUEST_PARTICIPANTS = "Request Participants"
    FINANCE_ONLY = "Finance Only"
    AUDIT_ONLY = "Audit Only"


class SettlementStatus(StrEnum):
    PENDING = "Pending"
    BALANCED = "Balanced"
    RETURN_DUE = "Return Due"
    REIMBURSEMENT_DUE = "Reimbursement Due"
    CLOSED = "Closed"


class LegalHoldState(StrEnum):
    NONE = "None"
    ACTIVE = "Active"
    RELEASED = "Released"


class AuditAction(StrEnum):
    SUBMITTED = "Submitted"
    REVIEWED = "Reviewed"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    RETURNED = "Returned"
    CHANGED = "Changed"
    DELEGATED = "Delegated"
    PAYMENT_UPDATED = "Payment Updated"
    CANCELLED = "Cancelled"
    CLOSED = "Closed"
    EXCEPTION_RECORDED = "Exception Recorded"
    EXPORTED = "Exported"
    AUTHORIZATION_DENIED = "Authorization Denied"
    CONFIGURATION_CHANGED = "Configuration Changed"
    SIGNED_IN = "Signed In"
    SIGN_IN_FAILED = "Sign-in Failed"
    SIGNED_OUT = "Signed Out"

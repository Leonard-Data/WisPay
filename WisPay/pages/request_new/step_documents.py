"""Documents step (step 3) of the create-payment-request wizard.

Renders the per-request-type document checklist; each row tracks the
requirement matrix exposed by ``RequestCreateState`` and uploads stay in
session until durable storage lands.

Usage::

    from WisPay.pages.request_new.step_documents import step_documents

    rx.cond(RequestCreateState.step == 3, step_documents(), ...)
"""

from __future__ import annotations

import reflex as rx

from states.request_create import RequestCreateState
from WisPay.pages.request_new.catalogs import DOC_SLOTS


def doc_row(key: str, label: str) -> rx.Component:
    """Render one checklist row for a known slot; visibility tracks the matrix.

    Args:
        key: Document slot code (e.g. ``"invoice"``).
        label: Human-readable slot name.

    Usage::
        doc_row("invoice", "Invoice")
    """

    listed = RequestCreateState.doc_keys.contains(key)
    met = RequestCreateState.uploaded_keys.contains(key)
    return rx.cond(
        listed,
        rx.el.div(
            rx.el.span(class_name=rx.cond(met, "wispay-new-dot is-met", "wispay-new-dot")),
            rx.el.div(
                rx.el.span(label, class_name="wispay-new-doc-title"),
                rx.el.span(
                    rx.cond(
                        met,
                        "Attached in this session",
                        rx.cond(
                            RequestCreateState.required_doc_keys.contains(key),
                            "Required before submission",
                            "Optional support",
                        ),
                    ),
                    class_name="wispay-new-doc-meta",
                ),
            ),
            rx.el.div(
                rx.cond(
                    met,
                    rx.el.button(
                        "Remove",
                        type="button",
                        on_click=RequestCreateState.remove_upload(key),  # type: ignore[operator]
                    ),
                    rx.el.div(
                        rx.upload(
                            rx.el.span("Choose file", class_name="wispay-new-upload-label"),
                            id=f"upload-{key}",
                            multiple=False,
                            accept={
                                "application/pdf": [".pdf"],
                                "image/png": [".png"],
                                "image/jpeg": [".jpg", ".jpeg"],
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
                                    ".xlsx"
                                ],
                            },
                            max_files=1,
                            class_name="wispay-new-upload-zone",
                        ),
                        rx.el.button(
                            "Attach",
                            type="button",
                            class_name="wispay-button wispay-button-primary wispay-new-attach",
                            on_click=RequestCreateState.handle_upload(
                                rx.upload_files(upload_id=f"upload-{key}")  # type: ignore[operator]
                            ),
                        ),
                        class_name="wispay-new-upload-group",
                    ),
                ),
                class_name="wispay-new-doc-actions",
            ),
            class_name=rx.cond(met, "wispay-new-doc-row is-met", "wispay-new-doc-row"),
        ),
        rx.fragment(),
    )


def step_documents() -> rx.Component:
    """Render the full Documents step panel with its checklist and limits.

    Usage::
        rx.cond(RequestCreateState.step == 3, step_documents(), ...)
    """

    return rx.el.section(
        rx.el.p("Step 3 · Documents", class_name="wispay-new-eyebrow"),
        rx.el.h2("Supporting documents", class_name="wispay-new-h3", tabindex="-1"),
        rx.el.p(
            "Attach the evidence reviewers need. Files stay in this session until "
            "durable storage lands.",
            class_name="wispay-new-muted",
        ),
        rx.el.div(
            *[doc_row(key, label) for key, label in DOC_SLOTS],
            class_name="wispay-new-doc-checklist wispay-new-card",
        ),
        rx.el.p(
            "Accepted: PDF, PNG, JPG, or XLSX up to 10 MB per file.",
            class_name="wispay-new-callout wsp-note",
        ),
        class_name="wispay-new-panel",
    )

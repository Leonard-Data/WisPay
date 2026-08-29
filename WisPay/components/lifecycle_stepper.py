"""Lifecycle stepper component for the request-detail and Finance Review screens.

Renders the 7-milestone Request-to-Pay lifecycle as a numbered horizontal
list. Branches (Returned, Rejected, Cancelled) are represented by a `×` glyph
plus a danger tone; the active step uses a focus ring per
``DESIGN.md#Lifecycle stepper``.

Usage::

    from WisPay.components.lifecycle_stepper import lifecycle_stepper, LifecycleStep

    lifecycle_stepper(
        LifecycleStep("Submitted", phase="done"),
        LifecycleStep("Budget Review", phase="done"),
        LifecycleStep("Approved", phase="active"),
        LifecycleStep("Payment in Process", phase="future"),
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import reflex as rx


class StepPhase:
    """Phase identifiers for the lifecycle stepper."""

    DONE: ClassVar[str] = "done"
    ACTIVE: ClassVar[str] = "active"
    FUTURE: ClassVar[str] = "future"
    BRANCH: ClassVar[str] = "branch"


@dataclass(frozen=True, slots=True)
class LifecycleStep:
    """A single step rendered in the lifecycle stepper."""

    label: str
    phase: str = StepPhase.FUTURE
    timestamp: str = ""


def _step_dot(step: LifecycleStep, index: int) -> rx.Component:
    """Render the numbered/branch glyph for one step."""

    return rx.el.span(
        rx.cond(
            step.phase == StepPhase.BRANCH,
            "\u00d7",
            rx.text(f"{index + 1}"),
        ),
        class_name="wispay-detail-step-dot",
    )


def lifecycle_stepper(*steps: LifecycleStep) -> rx.Component:
    """Render a horizontal lifecycle stepper.

    Args:
        *steps: The ordered lifecycle steps to display.

    Usage::

        lifecycle_stepper(
            LifecycleStep("Submitted", phase=StepPhase.DONE),
            LifecycleStep("Approved", phase=StepPhase.ACTIVE),
        )
    """

    if not steps:
        return rx.fragment()

    items: list[rx.Component] = []
    for index, step in enumerate(steps):
        glyph = (
            rx.el.span("\u00d7", class_name="wispay-detail-step-dot")
            if step.phase == StepPhase.BRANCH
            else rx.el.span(str(index + 1), class_name="wispay-detail-step-dot")
        )
        items.append(
            rx.el.li(
                glyph,
                rx.el.span(step.label, class_name="wispay-detail-step-label"),
                rx.cond(
                    step.timestamp != "",
                    rx.el.span(step.timestamp, class_name="wispay-detail-step-time"),
                    rx.fragment(),
                ),
                class_name=f"wispay-detail-step is-{step.phase}",
                key=f"step-{index}",
            )
        )

    return rx.el.ol(
        *items,
        aria_label="Request lifecycle",
        class_name="wispay-detail-stepper",
    )


def stepper_for_state(current_label: str) -> rx.Component:
    """Build a 7-milestone stepper from the active label only.

    Args:
        current_label: The label of the currently active step.

    Returns:
        A lifecycle stepper where the matching step is marked active, all
        prior steps are marked done, and remaining steps are future.

    Usage::

        stepper_for_state("Budget Review")
    """

    milestones: tuple[str, ...] = (
        "Submitted",
        "Budget Review",
        "Compliance Review",
        "Evidence Validation",
        "Approval Pending",
        "Approved",
        "Closed",
    )
    try:
        active_index = milestones.index(current_label)
    except ValueError:
        active_index = -1

    steps: list[LifecycleStep] = []
    for index, label in enumerate(milestones):
        if active_index < 0 or index < active_index:
            phase = StepPhase.DONE
        elif index == active_index:
            phase = StepPhase.ACTIVE
        else:
            phase = StepPhase.FUTURE
        steps.append(LifecycleStep(label=label, phase=phase))

    return lifecycle_stepper(*steps)


__all__ = [
    "LifecycleStep",
    "StepPhase",
    "lifecycle_stepper",
    "stepper_for_state",
]

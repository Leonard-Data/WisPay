"""Persona switching state adapter.

A thin UI adapter over the prototype persona roster defined in
:mod:`WisPay.services.demo_seed`. Pure server-side state (no driver
imports); routes consume the active persona id for permission checks.
"""

from __future__ import annotations

import reflex as rx

from WisPay.services.demo_seed import (
    DemoPersona,
    default_personas,
)


def _roster() -> tuple[DemoPersona, ...]:
    return default_personas()


class PersonaState(rx.State):
    """Active persona selection; consumed by A13 navigation checks."""

    active_persona_id: str = ""

    @rx.var
    def persona_options(self) -> list[dict[str, str]]:
        """Persona rows surfaced in the sidebar switcher (A13 hook)."""

        return [
            {
                "id": persona.snapshot.external_identity_id,
                "name": persona.snapshot.display_name,
                "email": persona.snapshot.email,
                "roles": ", ".join(role.value for role in persona.roles),
            }
            for persona in _roster()
        ]

    @rx.event
    def set_active_persona(self, persona_id: str) -> None:
        """Switch the active persona; reset to default when unknown."""

        known = {persona.snapshot.external_identity_id for persona in _roster()}
        self.active_persona_id = persona_id if persona_id in known else ""

    @rx.event
    def ensure_default(self) -> None:
        """Make sure a persona is selected on first hydration."""

        if self.active_persona_id:
            return
        roster = _roster()
        if roster:
            self.active_persona_id = roster[0].snapshot.external_identity_id


__all__ = ["PersonaState"]

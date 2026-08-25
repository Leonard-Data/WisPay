"""Shared UI state used by the application shell."""

from __future__ import annotations

import reflex as rx


class BaseState(rx.State):
    """State for shell-level interactions that are independent of a page."""

    sidebar_open: bool = False
    is_collapsed: bool = False
    workspace_group_open: bool = True
    review_group_open: bool = True
    operations_group_open: bool = True
    governance_group_open: bool = True

    @rx.event
    def toggle_sidebar(self) -> None:
        """Open or close the responsive navigation drawer."""
        self.sidebar_open = not self.sidebar_open

    @rx.event
    def close_sidebar(self) -> None:
        """Close the responsive navigation drawer."""
        self.sidebar_open = False

    @rx.event
    def toggle_sidebar_collapsed(self) -> None:
        """Toggle the compact desktop navigation rail."""
        self.is_collapsed = not self.is_collapsed

    @rx.event
    def toggle_workspace_group(self) -> None:
        """Toggle the Workspace navigation group."""
        self.workspace_group_open = not self.workspace_group_open

    @rx.event
    def toggle_review_group(self) -> None:
        """Toggle the Review navigation group."""
        self.review_group_open = not self.review_group_open

    @rx.event
    def toggle_operations_group(self) -> None:
        """Toggle the Operations navigation group."""
        self.operations_group_open = not self.operations_group_open

    @rx.event
    def toggle_governance_group(self) -> None:
        """Toggle the Governance navigation group."""
        self.governance_group_open = not self.governance_group_open

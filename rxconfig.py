"""Reflex configuration for the WisPay application.

Driver selection (BE-1):

- ``WS_DB_URL`` is the canonical knob. When set, it is forwarded to Reflex.
- When unset and ``AZURE_SQL_*`` env vars are populated, the legacy Azure SQL
  assembly is used (production).
- When neither is present, the dev default ``sqlite:///wispay.db`` is used
  so a fresh checkout can ``uv run reflex run`` without configuring a database.

Secrets stay in ``.env`` only (CONVENTIONS.md security rules).
"""

from __future__ import annotations

import os

import reflex as rx
from dotenv import load_dotenv
from reflex.plugins.shared_tailwind import TailwindConfig

load_dotenv()


def _resolve_db_url() -> str:
    """Resolve the effective DB URL for Reflex (SQLAlchemy-style)."""
    explicit = os.getenv("WS_DB_URL")
    if explicit:
        return explicit
    # Azure SQL is the production path: when both server and database env vars
    # are present, assemble the legacy connection string. The required ODBC
    # driver is an optional extra (`uv sync --extra azure`).
    if os.getenv("AZURE_SQL_SERVER") and os.getenv("AZURE_SQL_DATABASE"):
        username = os.getenv("AZURE_SQL_USERNAME", "")
        password = os.getenv("AZURE_SQL_PASSWORD", "")
        server = os.getenv("AZURE_SQL_SERVER", "").removeprefix("tcp:")
        database = os.getenv("AZURE_SQL_DATABASE", "")
        return (
            f"mssql+pyodbc://{username}:{password}"
            f"@{server}.database.windows.net/{database}"
            "?driver=ODBC+Driver+18+for+SQL+Server"
            "&Encrypt=yes"
            "&TrustServerCertificate=no"
            "&Connection+Timeout=30"
        )
    return "sqlite:///wispay.db"


db_url = _resolve_db_url()

config = rx.Config(
    app_name="WisPay",
    db_url=db_url,
    show_built_with_reflex=False,
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(
                accent_color="red",
                gray_color="gray",
                radius="medium",
            )
        ),
        rx.plugins.TailwindV4Plugin(
            TailwindConfig(
                darkMode="class",
                plugins=["@tailwindcss/typography", "tailwind-scrollbar"],
                theme={
                    "extend": {
                        "colors": {
                            "background": "var(--background)",
                            "foreground": "var(--foreground)",
                            "card": "var(--card)",
                            "card-foreground": "var(--card-foreground)",
                            "popover": "var(--popover)",
                            "popover-foreground": "var(--popover-foreground)",
                            "primary": "var(--primary)",
                            "primary-foreground": "var(--primary-foreground)",
                            "secondary": "var(--secondary)",
                            "secondary-foreground": "var(--secondary-foreground)",
                            "muted": "var(--muted)",
                            "muted-foreground": "var(--muted-foreground)",
                            "accent": "var(--accent)",
                            "accent-foreground": "var(--accent-foreground)",
                            "destructive": "var(--destructive)",
                            "border": "var(--border)",
                            "input": "var(--input)",
                            "ring": "var(--ring)",
                            "chart-1": "var(--chart-1)",
                            "chart-2": "var(--chart-2)",
                            "chart-3": "var(--chart-3)",
                            "chart-4": "var(--chart-4)",
                            "chart-5": "var(--chart-5)",
                            "sidebar": "var(--sidebar)",
                            "sidebar-foreground": "var(--sidebar-foreground)",
                            "sidebar-primary": "var(--sidebar-primary)",
                            "sidebar-primary-foreground": "var(--sidebar-primary-foreground)",
                            "sidebar-accent": "var(--sidebar-accent)",
                            "sidebar-accent-foreground": "var(--sidebar-accent-foreground)",
                            "sidebar-border": "var(--sidebar-border)",
                            "sidebar-ring": "var(--sidebar-ring)",
                        },
                        "fontFamily": {
                            "theme": "var(--font-family)",
                        },
                        "borderRadius": {
                            "radius": "var(--radius)",
                        },
                        "padding": {
                            "card": "var(--card-padding)",
                        },
                        "gap": {
                            "card": "var(--card-gap)",
                        },
                        "boxShadow": {
                            "default": "var(--shadow)",
                        },
                    }
                },
            )
        ),
    ],
)

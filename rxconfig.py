import os

import reflex as rx
from dotenv import load_dotenv
from reflex.plugins.shared_tailwind import TailwindConfig

load_dotenv()

required = {
    "AZURE_SQL_SERVER": os.getenv("AZURE_SQL_SERVER"),
    "AZURE_SQL_DATABASE": os.getenv("AZURE_SQL_DATABASE"),
    "AZURE_SQL_USERNAME": os.getenv("AZURE_SQL_USERNAME"),
    "AZURE_SQL_PASSWORD": os.getenv("AZURE_SQL_PASSWORD"),
}
# Construct the Azure SQL Server connection string
# Encrypt=yes and TrustServerCertificate=no are required by Azure SQL
connection_string = (
    f"mssql+pyodbc://{required['AZURE_SQL_USERNAME']}:{required['AZURE_SQL_PASSWORD']}@{required['AZURE_SQL_SERVER']}.database.windows.net/{required['AZURE_SQL_DATABASE']}"
    "?driver=ODBC+Driver+18+for+SQL+Server"
    "&Encrypt=yes"
    "&TrustServerCertificate=no"
    "&Connection+Timeout=30"
)

config = rx.Config(
    app_name="WisPay",
    db_url=connection_string,
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

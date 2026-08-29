"""Production server entry point for the WisPay container.

The Dockerfile invokes ``python -m scripts.serve`` so the same command
works in dev (no Dockerfile) and prod (inside the container). We wrap
the canonical ``reflex run --env prod`` invocation so the configured
``APP_HOST`` / ``APP_PORT`` environment variables flow through to the
ASGI server.

Kept intentionally small so the boot path stays auditable: any change
to the production server is one file in this repo, not a runtime script
hidden in a container layer.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    """Run the production server, returning the child process exit code."""

    host = os.environ.get("APP_HOST", "0.0.0.0")
    port = int(os.environ.get("APP_PORT", "8000"))

    # ``reflex run --env prod`` serves the compiled frontend bundle from
    # .web alongside the ASGI backend. The frontend port is implicit
    # (mounted under the backend port), so the host system only needs
    # to forward a single TCP port.
    cmd = [
        "reflex",
        "run",
        "--env",
        "prod",
        "--backend-host",
        host,
        "--backend-port",
        str(port),
    ]
    print("Starting WisPay:", " ".join(cmd), flush=True)
    try:
        import subprocess
    except ImportError:
        os.execvp(cmd[0], cmd)
        return 0  # unreachable
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())

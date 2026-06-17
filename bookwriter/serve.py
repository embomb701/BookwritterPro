"""Launcher: ``python -m bookwriter.serve``.

Runs uvicorn on 127.0.0.1:8000 (override via BOOKWRITER_HOST / BOOKWRITER_PORT)
serving ``bookwriter.server.create_app()``. Keep heavy imports inside main() so
this module stays cheap to import.
"""
from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    from .server import create_app

    host = os.environ.get("BOOKWRITER_HOST", "127.0.0.1")
    port = int(os.environ.get("BOOKWRITER_PORT", "8000"))

    app = create_app()
    print(f"BookwriterPro server: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

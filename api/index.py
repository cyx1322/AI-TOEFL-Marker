"""Vercel entrypoint for the FastAPI application."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_app():
    """Dynamically load the primary FastAPI app from api.py."""
    module_name = "ai_toefl_app"
    if module_name in sys.modules:
        module = sys.modules[module_name]
    else:
        project_root = Path(__file__).resolve().parent.parent
        module_path = project_root / "api.py"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("Unable to locate api.py for import.")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    app = getattr(module, "app", None)
    if app is None:
        raise RuntimeError("api.py does not expose a FastAPI instance named 'app'.")
    return app


app = _load_app()
handler = app  # Vercel uses `handler`/`app` for ASGI-compatible runtimes.

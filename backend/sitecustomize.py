"""Compatibility hook for source-controlled training runtime patches.

Python imports ``sitecustomize`` automatically when available. The FastAPI
application also installs the same patches explicitly, so this hook remains a
safe compatibility layer for scripts and local utilities.
"""
from __future__ import annotations

try:
    from app.services.training_runtime_patches import install_training_runtime_patches

    install_training_runtime_patches()
except Exception:
    # Some build/bootstrap Python invocations run before application
    # dependencies are installed. FastAPI startup installs the patches again
    # and fails visibly if the approved runtime behavior cannot be activated.
    pass

"""Keep Python interpreter startup free of application side effects.

Training runtime behavior is installed explicitly from ``app.main`` where
failures are visible to the application and deployment logs. Importing database,
PDF and question-bank modules from ``sitecustomize`` caused every Python process
(including platform supervisors and migration tools) to perform heavy application
initialization before its real entrypoint.

This compatibility module intentionally performs no application imports.
"""
from __future__ import annotations

SITE_CUSTOMIZE_SIDE_EFFECT_FREE = True

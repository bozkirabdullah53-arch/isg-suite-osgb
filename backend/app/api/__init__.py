"""API package bootstrap.

The AI gateway extension is attached additively to the existing EİSA router.
No existing route is replaced.
"""
from . import eisa as eisa
from .eisa_ai_gateway import router as _ai_gateway_router
from app.services.ai_gateway_config import install_runtime_hook

eisa.router.include_router(_ai_gateway_router)
install_runtime_hook()

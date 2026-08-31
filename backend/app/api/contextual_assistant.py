from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.api.deps import get_current_user
from app.core.config import contextual_assistant_active
from app.models.entities import User
from app.services.contextual_assistant import UNAVAILABLE_MESSAGE, answer

router = APIRouter(prefix="/assistant", tags=["Contextual OHS Assistant"])

class ContextualAssistantRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    context: dict = Field(default_factory=dict)

@router.post("/contextual")
def contextual_assistant(payload: ContextualAssistantRequest, user: User = Depends(get_current_user)):
    if not contextual_assistant_active():
        raise HTTPException(status_code=503, detail=UNAVAILABLE_MESSAGE)
    try:
        return answer(question=payload.question, raw_context=payload.context, user=user)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=UNAVAILABLE_MESSAGE) from exc

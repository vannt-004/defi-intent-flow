from fastapi import APIRouter, HTTPException

from portfolio_engine.services.assistant_service import AssistantService

router = APIRouter(prefix="/assistant", tags=["Assistant"])


@router.post("")
async def assistant_reply(payload: dict):
    service = AssistantService()
    result = await service.reply(payload)
    if result.get("error") == "empty_prompt":
        raise HTTPException(status_code=400, detail="empty_prompt")
    return result

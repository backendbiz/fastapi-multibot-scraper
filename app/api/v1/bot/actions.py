from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.core.security.api_key import get_api_key
from app.worker.tasks import pandamaster_action

router = APIRouter()

class BotActionRequest(BaseModel):
    action_type: str = Field(..., description="Type of action: agent_balance, deposit, redeem, etc.")
    username: Optional[str] = None
    amount: Optional[float] = None
    game_game: str = Field(..., description="Target game, e.g. pandamaster")
    metadata: Optional[dict] = Field(default={}, description="Additional data for the task")

@router.post("/action", response_model=dict)
async def trigger_bot_action(
    request: BotActionRequest,
#    api_key: str = Depends(get_api_key) # Uncomment to enforce API Key auth
):
    """
    Trigger a bot action in the background.
    """
    if request.game_game not in ["pandamaster", "firekirin", "orionstars", "milkywayapp", "juwa777", "vegasx", "vblink777"]:
        raise HTTPException(status_code=400, detail="Supported games: pandamaster, firekirin, orionstars, milkywayapp, juwa777, vegasx, vblink777")
        
    # Queue the task in Celery
    task = pandamaster_action.delay(
        action_type=request.action_type,
        game_name=request.game_game,
        username=request.username,
        amount=request.amount,
        metadata=request.metadata
    )
    
    return {
        "status": "queued",
        "task_id": task.id,
        "message": f"Action {request.action_type} for {request.game_game} queued."
    }

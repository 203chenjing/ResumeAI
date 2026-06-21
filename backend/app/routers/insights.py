"""洞察 API：用户账号、跟进提醒、拒信分析。"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.models.schemas import ApiResponse
from app.services.analyze_patterns import analyze_patterns
from app.services.followup_reminders import followup_reminders
from app.services.user_account import get_profile, save_profile

router = APIRouter(prefix="/api", tags=["insights"])


class ProfileBody(BaseModel):
    client_id: str = "default"
    display_name: str = ""
    email: str = ""
    school: str = ""
    major: str = ""
    graduation_year: str = ""
    target_roles: list[str] | None = None
    weekly_apply_limit: int = 15
    min_match_score: int = 60


@router.get("/user-profile/{client_id}", response_model=ApiResponse)
async def get_user_profile(client_id: str):
    return ApiResponse(success=True, data=get_profile(client_id))


@router.put("/user-profile", response_model=ApiResponse)
async def put_user_profile(body: ProfileBody):
    profile = save_profile(body.client_id, body.model_dump())
    return ApiResponse(success=True, data=profile)


@router.get("/reminders/{client_id}", response_model=ApiResponse)
async def get_reminders(client_id: str):
    return ApiResponse(success=True, data={"reminders": followup_reminders(client_id)})


@router.get("/insights/patterns/{client_id}", response_model=ApiResponse)
async def get_patterns(client_id: str):
    return ApiResponse(success=True, data=analyze_patterns(client_id))

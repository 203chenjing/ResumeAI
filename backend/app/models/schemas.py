"""数据模型定义。"""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


# ---------------- Resume ----------------
class ResumeHeader(BaseModel):
    name: str = ""
    phone: str = ""
    email: str = ""
    location: str = ""
    target_role: str = ""


class EducationEntry(BaseModel):
    school: str = ""
    college: str = ""  # 学院
    degree: str = ""
    major: str = ""
    start_date: str = ""
    end_date: str = ""
    gpa: str = ""
    courses: list[str] = []
    honors: list[str] = []


class ExperienceEntry(BaseModel):
    company: str = ""
    role: str = ""
    start_date: str = ""
    end_date: str = ""
    items: list[str] = []  # 编号经历条目，每条一句完整描述


class ParsedResume(BaseModel):
    header: ResumeHeader = ResumeHeader()
    education: list[EducationEntry] = []
    experience: list[ExperienceEntry] = []
    skills: dict[str, str] = {}  # {工作技能/数据技能/AI技能/语言能力: "..."}
    raw_markdown: str = ""


# ---------------- JD ----------------
class JDAnalysis(BaseModel):
    role: str = ""
    company: str = ""
    archetype: str = ""  # 岗位原型: AI产品/数据分析/前端/后端/运营/...（借鉴 career-ops）
    core_requirements: list[str] = []
    preferred_requirements: list[str] = []
    keywords: list[str] = []
    soft_skills: list[str] = []
    industry_terms: list[str] = []
    legitimacy_score: int = 100  # JD 真实性 0-100（识别假招聘）
    legitimacy_flags: list[str] = []  # 可疑信号：「无具体公司」「薪资远超行业」「邮箱可疑」等
    ranking: dict[str, list[str]] = Field(default_factory=lambda: {
        "核心匹配": [],
        "可强化匹配": [],
        "不相关/弱相关": [],
    })


# ---------------- Match ----------------
class MatchDimension(BaseModel):
    name: str
    score: int  # 0-100
    max: int = 100


class GapItem(BaseModel):
    requirement: str
    status: Literal["match", "partial", "missing"]
    detail: str = ""


class MatchResult(BaseModel):
    overall_score: int = 0
    dimensions: list[MatchDimension] = []
    gap_analysis: list[GapItem] = []


# ---------------- Suggestion ----------------
SuggestionType = Literal["wording", "star", "keyword", "structure", "delete"]
SuggestionStatus = Literal["pending", "accepted", "rejected", "adjusted"]


class Suggestion(BaseModel):
    id: str
    section: str  # education / experience / skills / header
    type: SuggestionType
    original_text: str
    suggested_text: str
    reason: str
    jd_match_points: list[str] = []
    line_range: list[int] = [0, 0]  # [start, end]
    status: SuggestionStatus = "pending"


# ---------------- Chat ----------------
class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


# ---------------- Session ----------------
class Session(BaseModel):
    session_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)
    original_resume_md: str = ""
    parsed_resume: ParsedResume | None = None
    jd_text: str = ""
    knowledge_base_md: str = ""
    profile_photo_ref: str = ""  # uploads/{session_id}/profile-photo.png
    jd_analysis: JDAnalysis | None = None
    current_resume_md: str = ""
    finalized_resume_md: str = ""
    finalize_status: Literal["draft", "finalized", "stale"] = "draft"
    suggestions: list[Suggestion] = []
    chat_history: list[ChatMessage] = []
    match_result: MatchResult | None = None
    status: str = "uploading"
    agent_prefs: dict = Field(default_factory=dict)


# ---------------- API Response ----------------
class ApiResponse(BaseModel):
    success: bool = True
    data: dict | list | None = None
    error: str | None = None

"""FastAPI 应用入口。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.crawl_scheduler import start_crawl_scheduler, stop_crawl_scheduler
from app.services.crawl_task import STUDIO_PATH_PREFIXES
from app.services.llm_priority import studio_enter, studio_leave
from app.routers import (
    agent,
    analysis,
    applications,
    career_copilot,
    chat,
    chat_agent,
    export,
    finalize,
    hub,
    insights,
    interview,
    jd,
    jobs,
    knowledge,
    knowledge_agent,
    master_resume,
    memory,
    pending_knowledge,
    resume,
    session,
    suggestion,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_crawl_scheduler()
    yield
    stop_crawl_scheduler()


app = FastAPI(
    title="AI 简历修改 API",
    version="1.0.0",
    description="JD 驱动的简历智能修改后端",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def studio_priority_middleware(request, call_next):
    """改稿 API 进行中时，爬虫 enrichment 主动让路。"""
    path = request.url.path
    if any(path.startswith(p) for p in STUDIO_PATH_PREFIXES):
        studio_enter()
        try:
            return await call_next(request)
        finally:
            studio_leave()
    return await call_next(request)


app.include_router(resume.router)
app.include_router(jd.router)
app.include_router(analysis.router)
app.include_router(suggestion.router)
app.include_router(chat.router)
app.include_router(chat_agent.router)
app.include_router(agent.router)
app.include_router(memory.router)
app.include_router(export.router)
app.include_router(finalize.router)
app.include_router(knowledge.router)
app.include_router(knowledge_agent.router)
app.include_router(pending_knowledge.router)
app.include_router(applications.router)
app.include_router(session.router)
app.include_router(jobs.router)
app.include_router(hub.router)
app.include_router(career_copilot.router)
app.include_router(master_resume.router)
app.include_router(interview.router)
app.include_router(insights.router)


@app.get("/health")
async def health():
    return {"status": "ok", "model": settings.deepseek_model}


@app.get("/")
async def root():
    return {
        "service": "AI 简历修改 API",
        "version": "1.0.0",
        "health": "/health",
        "docs": "/docs",
    }

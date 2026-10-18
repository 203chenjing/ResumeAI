"""FastAPI 应用入口。"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.crawl_scheduler import start_crawl_scheduler, stop_crawl_scheduler
from app.services.crawl_task import STUDIO_PATH_PREFIXES
from app.services.llm_client import (
    LLMNotConfiguredError,
    LLMUpstreamError,
    client as llm_client,
)
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

logger = logging.getLogger("app.main")

SLOW_REQUEST_SECONDS = 5.0


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not llm_client.configured:
        logger.warning(
            "未配置 DEEPSEEK_API_KEY：AI 相关接口将返回 503。请在 backend/.env 填入 Key 后重启。"
        )
    start_crawl_scheduler()
    yield
    stop_crawl_scheduler()
    await llm_client.aclose()


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


@app.middleware("http")
async def request_timing_middleware(request, call_next):
    """记录慢请求，便于排查前端「转圈很久」到底卡在哪个接口。"""
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    if elapsed >= SLOW_REQUEST_SECONDS:
        logger.warning(
            "slow request %s %s -> %s (%.1fs)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
    return response


@app.exception_handler(LLMNotConfiguredError)
async def llm_not_configured_handler(_request: Request, exc: LLMNotConfiguredError):
    """配置缺失是可修复问题：503 + 明确指引，而不是 500 + 堆栈。"""
    logger.error("LLM not configured: %s", exc)
    return JSONResponse(
        status_code=503,
        content={
            "success": False,
            "code": "llm_not_configured",
            "detail": str(exc),
        },
    )


@app.exception_handler(LLMUpstreamError)
async def llm_upstream_handler(_request: Request, exc: LLMUpstreamError):
    logger.error("LLM upstream error (%s): %s", exc.status_code, exc)
    return JSONResponse(
        status_code=502 if exc.status_code != 429 else 429,
        content={
            "success": False,
            "code": "llm_upstream_error",
            "detail": str(exc),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    """兜底：对外只给可读信息，堆栈留在服务端日志。"""
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "code": "internal_error",
            "detail": "服务内部错误，请查看后端日志（_deploy_logs 或终端输出）",
        },
    )


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
    return {
        "status": "ok",
        "model": settings.deepseek_model,
        "llm_configured": llm_client.configured,
    }


@app.get("/")
async def root():
    return {
        "service": "AI 简历修改 API",
        "version": "1.0.0",
        "health": "/health",
        "docs": "/docs",
    }

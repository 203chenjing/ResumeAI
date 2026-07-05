"""岗位发现 + 多 JD 对比 API。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.schemas import ApiResponse
from app.crawlers.crawl_config import load_crawl_config, reload_crawl_config
from app.crawlers.wechat_article import WechatArticleProvider
from app.services.crawl_health import get_crawl_health, get_crawl_history, record_crawl_run
from app.services.crawl_task import get_crawl_state, start_crawl
from app.services.browser_discovery import run_browser_discovery_pipeline
from app.services.wechat_discovery import run_wechat_discovery_pipeline
from app.services.job_cohort import backfill_graduation_cohort
from app.services.job_digest import build_job_digest, load_digest
from app.services.job_feed import add_job, crawl_all, crawl_comprehensive, cross_verify_feed, dedupe_feed, feed_meta, list_jobs, merge_fetched_jobs, organize_feed
from app.services.job_preferences import load_job_preferences, save_job_preferences
from app.services.master_resume import get_active_master
from app.services.match_engine import rerank_jobs
from app.services.multi_jd_compare import compare_jobs
from app.services.user_memory import load_memory

router = APIRouter(prefix="/api", tags=["jobs"])


class CrawlBody(BaseModel):
    client_id: str = "default"
    providers: list[str] | None = None


class DedupeBody(BaseModel):
    client_id: str = "default"


class CompareBody(BaseModel):
    client_id: str = "default"
    job_ids: list[str] = Field(default_factory=list)
    resume_md: str = ""


class IngestWechatBody(BaseModel):
    client_id: str = "default"
    url: str


class JobPreferencesBody(BaseModel):
    client_id: str = "default"
    target_roles: list[str] = Field(default_factory=list)
    target_cities: list[str] = Field(default_factory=list)
    job_types: list[str] = Field(default_factory=list)
    target_cohort: str = "27届"
    include_unknown_cohort: bool = True
    company_wishlist: list[str] = Field(default_factory=list)
    company_blocklist: list[str] = Field(default_factory=list)
    extra_notes: str = ""


class DigestBody(BaseModel):
    client_id: str = "default"
    new_job_ids: list[str] = Field(default_factory=list)


class RerankBody(BaseModel):
    client_id: str = "default"
    top_k: int = 20
    resume_md: str = ""


@router.get("/jobs/feed/{client_id}", response_model=ApiResponse)
async def get_feed(
    client_id: str,
    source: str | None = None,
    job_type: str | None = None,
    work_city: str | None = None,
    graduation_cohort: str | None = None,
    include_unknown_cohort: bool | None = None,
    include_weak: bool = True,
):
    prefs = load_job_preferences(client_id)
    if graduation_cohort is not None:
        cohort = graduation_cohort.strip() or None
        include_unknown = True if include_unknown_cohort is None else include_unknown_cohort
    else:
        cohort = (prefs.get("target_cohort") or "").strip() or None
        include_unknown = (
            prefs.get("include_unknown_cohort", True)
            if include_unknown_cohort is None
            else include_unknown_cohort
        )
    jobs = list_jobs(
        client_id,
        source,
        job_type=job_type,
        work_city=work_city,
        graduation_cohort=cohort,
        include_unknown_cohort=include_unknown,
        include_weak=include_weak,
    )
    return ApiResponse(
        success=True,
        data={"jobs": jobs, "meta": feed_meta(client_id), "digest": load_digest(client_id)},
    )


@router.get("/jobs/preferences/{client_id}", response_model=ApiResponse)
async def get_job_preferences(client_id: str):
    return ApiResponse(success=True, data=load_job_preferences(client_id))


@router.put("/jobs/preferences", response_model=ApiResponse)
async def put_job_preferences(body: JobPreferencesBody):
    saved = save_job_preferences(
        body.client_id,
        {
            "target_roles": body.target_roles,
            "target_cities": body.target_cities,
            "job_types": body.job_types,
            "target_cohort": body.target_cohort,
            "include_unknown_cohort": body.include_unknown_cohort,
            "company_wishlist": body.company_wishlist,
            "company_blocklist": body.company_blocklist,
            "extra_notes": body.extra_notes,
        },
    )
    return ApiResponse(success=True, data=saved)


@router.get("/jobs/digest/{client_id}", response_model=ApiResponse)
async def get_job_digest(client_id: str):
    digest = load_digest(client_id)
    return ApiResponse(success=True, data=digest)


@router.post("/jobs/digest", response_model=ApiResponse)
async def post_job_digest(body: DigestBody):
    digest = await build_job_digest(body.client_id, new_job_ids=body.new_job_ids or None)
    return ApiResponse(success=True, data=digest)


@router.post("/jobs/crawl", response_model=ApiResponse)
async def post_crawl(body: CrawlBody):
    """启动后台爬虫，立即返回，可与改稿并行。"""
    state = await start_crawl(body.client_id, body.providers)
    data = state.to_api()
    if state.status == "running" and not state.result:
        data["message"] = "爬虫已在后台运行，可继续改简历"
    return ApiResponse(success=True, data=data)


@router.get("/jobs/crawl-status/{client_id}", response_model=ApiResponse)
async def get_crawl_status(client_id: str):
    state = await get_crawl_state()
    if state.status == "idle" or (state.status == "running" and state.client_id != client_id):
        return ApiResponse(success=True, data={"status": "idle"})
    return ApiResponse(success=True, data=state.to_api())


@router.post("/jobs/crawl-sync", response_model=ApiResponse)
async def post_crawl_sync(body: CrawlBody):
    """同步爬虫（测试/脚本用），会阻塞至完成。"""
    result = await crawl_all(body.client_id, body.providers)
    health = record_crawl_run(
        body.client_id,
        report=result.get("report") or [],
        new_count=result.get("new_count", 0),
        total=result.get("total", 0),
    )
    new_ids = [j.get("id") for j in result.get("new_jobs") or [] if j.get("id")]
    digest = await build_job_digest(body.client_id, new_job_ids=new_ids)
    return ApiResponse(
        success=True,
        data={
            "new_count": result["new_count"],
            "total": result["total"],
            "report": result["report"],
            "quality": result.get("quality"),
            "jobs": list_jobs(body.client_id),
            "digest": digest,
            "crawl_health": health,
        },
    )


@router.post("/jobs/dedupe", response_model=ApiResponse)
async def post_dedupe(body: DedupeBody):
    stats = dedupe_feed(body.client_id)
    return ApiResponse(
        success=True,
        data={
            **stats,
            "jobs": list_jobs(body.client_id),
        },
    )


@router.post("/jobs/organize", response_model=ApiResponse)
async def post_organize(body: DedupeBody):
    """去重、过滤噪声、AI 解析 weak 岗位并重新排序。"""
    stats = await organize_feed(body.client_id)
    return ApiResponse(
        success=True,
        data={
            **stats,
            "jobs": list_jobs(body.client_id, include_weak=False),
            "meta": feed_meta(body.client_id),
        },
    )


@router.get("/jobs/crawl-config", response_model=ApiResponse)
async def get_crawl_config():
    cfg = load_crawl_config()
    # 不暴露内部实现细节，只返回源清单摘要
    sources_summary = []
    for pname, pconf in (cfg.get("providers") or {}).items():
        srcs = pconf.get("sources") or []
        sources_summary.append(
            {
                "provider": pname,
                "enabled": pconf.get("enabled", True),
                "source_count": len(srcs),
                "sources": [
                    {
                        "id": s.get("id"),
                        "name": s.get("name"),
                        "list_url": s.get("list_url"),
                        "enabled": s.get("enabled", True),
                    }
                    for s in srcs
                ],
            }
        )
    return ApiResponse(
        success=True,
        data={
            "compliance": cfg.get("compliance"),
            "providers": sources_summary,
            "config_path": "backend/crawl_sources.yml",
        },
    )


@router.post("/jobs/wechat-discover", response_model=ApiResponse)
async def post_wechat_discover(body: CrawlBody):
    """公众号专项：搜索→汇总页 harvest→逐篇阅读→AI 提取。"""
    from app.crawlers.crawl_config import get_provider_config

    cfg = get_provider_config("wechat_discovery")
    jobs, steps = await run_wechat_discovery_pipeline(cfg)
    fetched = [j.to_dict() for j in jobs]
    result = await merge_fetched_jobs(
        body.client_id,
        fetched,
        crawled_sources={"wechat_discovery"},
    )
    cross_stats = cross_verify_feed(body.client_id)
    return ApiResponse(
        success=True,
        data={
            "steps": steps,
            "new_count": result["new_count"],
            "total": result["total"],
            "quality": result.get("quality"),
            "cross_verify": cross_stats,
            "jobs": list_jobs(body.client_id),
            "meta": feed_meta(body.client_id),
        },
    )


@router.post("/jobs/browser-discover", response_model=ApiResponse)
async def post_browser_discover(body: CrawlBody):
    """仅运行浏览器五步流水线（搜索→访问→AI 提取），再交叉确认入库。"""
    from app.crawlers.crawl_config import get_provider_config

    cfg = get_provider_config("browser_discovery")
    jobs, steps = await run_browser_discovery_pipeline(cfg)
    fetched = [j.to_dict() for j in jobs]
    result = await merge_fetched_jobs(
        body.client_id,
        fetched,
        crawled_sources={"browser_discovery"},
    )
    cross_stats = cross_verify_feed(body.client_id)
    return ApiResponse(
        success=True,
        data={
            "steps": steps,
            "new_count": result["new_count"],
            "total": result["total"],
            "quality": result.get("quality"),
            "cross_verify": cross_stats,
            "jobs": list_jobs(body.client_id),
            "meta": feed_meta(body.client_id),
        },
    )


@router.post("/jobs/crawl-comprehensive", response_model=ApiResponse)
async def post_crawl_comprehensive(body: CrawlBody):
    """全渠道同步抓取 + 交叉确认（测试/脚本用）。"""
    result = await crawl_comprehensive(body.client_id)
    cross_stats = cross_verify_feed(body.client_id)
    health = record_crawl_run(
        body.client_id,
        report=result.get("report") or [],
        new_count=result.get("new_count", 0),
        total=result.get("total", 0),
    )
    new_ids = [j.get("id") for j in result.get("new_jobs") or [] if j.get("id")]
    digest = await build_job_digest(body.client_id, new_job_ids=new_ids)
    return ApiResponse(
        success=True,
        data={
            "new_count": result["new_count"],
            "total": result["total"],
            "report": result["report"],
            "quality": result.get("quality"),
            "cross_verify": cross_stats,
            "jobs": list_jobs(body.client_id),
            "digest": digest,
            "crawl_health": health,
        },
    )


@router.post("/jobs/cross-verify", response_model=ApiResponse)
async def post_cross_verify(body: DedupeBody):
    """对现有岗位库做多渠道交叉确认。"""
    stats = cross_verify_feed(body.client_id)
    return ApiResponse(success=True, data=stats)


@router.post("/jobs/backfill-cohort", response_model=ApiResponse)
async def post_backfill_cohort(body: DedupeBody):
    """回填现有岗位库的 graduation_cohort 字段。"""
    stats = backfill_graduation_cohort(body.client_id)
    return ApiResponse(
        success=True,
        data={
            **stats,
            "jobs": list_jobs(body.client_id, include_weak=True),
            "meta": feed_meta(body.client_id),
        },
    )


@router.post("/jobs/reload-config", response_model=ApiResponse)
async def post_reload_config():
    cfg = reload_crawl_config()
    return ApiResponse(success=True, data={"reloaded": True, "provider_count": len(cfg.get("providers") or {})})


@router.post("/jobs/ingest-wechat", response_model=ApiResponse)
async def ingest_wechat(body: IngestWechatBody):
    from app.crawlers.crawl_config import get_compliance
    from app.crawlers.fetcher import CrawlFetcher

    provider = WechatArticleProvider()
    fetcher = CrawlFetcher(get_compliance())
    try:
        job = await provider.ingest_url(body.url, fetcher=fetcher)
    finally:
        await fetcher.close()
    if not job:
        raise HTTPException(400, "无法解析 URL")
    saved = add_job(body.client_id, job.to_dict())
    return ApiResponse(success=True, data=saved)


@router.get("/jobs/crawl-health/{client_id}", response_model=ApiResponse)
async def get_jobs_crawl_health(client_id: str):
    return ApiResponse(success=True, data=get_crawl_health(client_id))


@router.get("/jobs/crawl-history/{client_id}", response_model=ApiResponse)
async def get_jobs_crawl_history(client_id: str, limit: int = 10):
    return ApiResponse(success=True, data={"history": get_crawl_history(client_id, limit)})


@router.post("/jobs/rerank", response_model=ApiResponse)
async def post_rerank(body: RerankBody):
    jobs = list_jobs(body.client_id, include_weak=False)
    resume_md = body.resume_md.strip()
    if not resume_md:
        master = get_active_master(body.client_id)
        if master:
            resume_md = master.get("markdown", "")
    if not resume_md:
        mem = load_memory(body.client_id)
        resume_md = mem.get("knowledge_base_md", "")
    if not resume_md:
        raise HTTPException(400, "请先保存母版简历或知识库")
    prefs = load_job_preferences(body.client_id)
    ranked = rerank_jobs(resume_md, jobs, prefs=prefs, top_k=min(body.top_k, 50))
    return ApiResponse(
        success=True,
        data={
            "algorithm": "hybrid_bm25_skill_jaccard",
            "count": len(ranked),
            "rows": [
                {
                    "job_id": r["job"].get("id"),
                    "company": r["job"].get("company"),
                    "role": r["job"].get("role"),
                    "hybrid_score": r["hybrid_score"],
                    "score_breakdown": r["score_breakdown"],
                    "match": r["match"].model_dump(),
                }
                for r in ranked
            ],
        },
    )


@router.post("/jobs/compare", response_model=ApiResponse)
async def post_compare(body: CompareBody):
    jobs = list_jobs(body.client_id)
    if body.job_ids:
        id_set = set(body.job_ids)
        jobs = [j for j in jobs if j.get("id") in id_set]
    if not jobs:
        raise HTTPException(400, "没有可对比的岗位，请先爬取或添加岗位")

    resume_md = body.resume_md.strip()
    if not resume_md:
        master = get_active_master(body.client_id)
        if master:
            resume_md = master.get("markdown", "")
    if not resume_md:
        mem = load_memory(body.client_id)
        resume_md = mem.get("knowledge_base_md", "")
    if not resume_md:
        raise HTTPException(400, "请先保存母版简历或知识库")

    rows = compare_jobs(resume_md, jobs, prefs=load_job_preferences(body.client_id))
    return ApiResponse(success=True, data={"rows": rows, "compared_count": len(rows)})

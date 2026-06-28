"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import { ROUTES } from "@/lib/navigation";
import { useAppStore } from "@/stores/useAppStore";
import { useCrawlStore } from "@/stores/useCrawlStore";
import type { JobDigest, JobFeedMeta, JobPosting } from "@/lib/types";
import {
  displayCompany,
  displayRole,
  facetTags,
  formatDateShort,
  freshnessLabel,
  positionTitles,
  publisherLabel,
  sourceLabel,
  workCities,
} from "@/lib/jobDisplay";
import {
  ExternalLink,
  Globe,
  Link2,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
} from "lucide-react";
import JobDigestPanel from "@/components/jobs/JobDigestPanel";
import JobPreferencesPanel from "@/components/jobs/JobPreferencesPanel";
import CareerCopilotPanel from "@/components/jobs/CareerCopilotPanel";
import type { CrawlHealth, CrawlRun } from "@/lib/types";
import { copy } from "@/lib/copy";

const PRIORITY_BADGE: Record<string, string> = {
  P0: "bg-[var(--semantic-danger-muted)] text-[var(--semantic-danger)]",
  P1: "bg-[var(--semantic-warning-muted)] text-[var(--semantic-warning)]",
  P2: "bg-[var(--surface-base)] text-[var(--text-secondary)]",
};

const SOURCE_OPTIONS = [
  { id: "", label: "全部来源" },
  { id: "job_aggregator", label: "求职平台" },
  { id: "company_campus", label: "企业官网" },
  { id: "university_html", label: "高校就业网" },
  { id: "wechat_article", label: "公众号" },
];

const TYPE_OPTIONS = ["", "实习", "校招", "提前批", "秋招", "春招", "补录"];

export default function JobsView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setStudioFromJob, setJdText } = useAppStore();
  const [jobs, setJobs] = useState<JobPosting[]>([]);
  const [meta, setMeta] = useState<JobFeedMeta | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [crawling, setCrawling] = useState(false);
  const [wechatUrl, setWechatUrl] = useState("");
  const [filter, setFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [cityFilter, setCityFilter] = useState("");
  const [hideWeak, setHideWeak] = useState(true);
  const [crawlReport, setCrawlReport] = useState("");
  const [digest, setDigest] = useState<JobDigest | null>(null);
  const [digestLoading, setDigestLoading] = useState(false);
  const [crawlHealth, setCrawlHealth] = useState<CrawlHealth | null>(null);
  const [crawlHistory, setCrawlHistory] = useState<CrawlRun[]>([]);

  const crawlUiStatus = useCrawlStore((s) => s.status);
  const lastResult = useCrawlStore((s) => s.lastResult);
  const setCrawlRunning = useCrawlStore((s) => s.setRunning);
  const consumeLastResult = useCrawlStore((s) => s.consumeLastResult);

  useEffect(() => {
    const q = searchParams.get("filter");
    if (q) setFilter(q);
  }, [searchParams]);

  async function load() {
    setLoading(true);
    try {
      const res = await api.getJobFeed(getClientId(), {
        source: sourceFilter || undefined,
        job_type: typeFilter || undefined,
        work_city: cityFilter || undefined,
        include_weak: !hideWeak,
      });
      if (res.success && res.data) {
        setJobs(res.data.jobs);
        setMeta(res.data.meta || null);
        if (res.data.digest) setDigest(res.data.digest);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [sourceFilter, typeFilter, cityFilter, hideWeak]);

  useEffect(() => {
    api.getCrawlHealth(getClientId()).then((res) => {
      if (res.success && res.data) setCrawlHealth(res.data);
    }).catch(() => {});
    api.getCrawlHistory(getClientId()).then((res) => {
      if (res.success && res.data) setCrawlHistory(res.data.history);
    }).catch(() => {});
    api.dedupeJobFeed(getClientId()).then((res) => {
      if (res.success && res.data && res.data.before !== res.data.after) load();
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!lastResult) return;
    applyCrawlResult(lastResult);
    consumeLastResult();
    void load();
  }, [lastResult, consumeLastResult]);

  useEffect(() => {
    if (crawlUiStatus === "running") {
      setCrawlReport(copy.crawl.backgroundHint);
    }
  }, [crawlUiStatus]);

  function applyCrawlResult(data: {
    new_count?: number;
    total?: number;
    quality?: { validated_ok?: number };
    jobs?: JobPosting[];
    digest?: JobDigest;
    crawl_health?: CrawlHealth;
  }) {
    if (data.jobs) setJobs(data.jobs);
    if (data.digest) setDigest(data.digest);
    const q = data.quality;
    const qualityLine = q ? `，其中 ${q.validated_ok ?? 0} 条可投递` : "";
    if (data.new_count != null && data.total != null) {
      setCrawlReport(`刷新完成：新增 ${data.new_count} 条，当前共 ${data.total} 条${qualityLine}`);
    }
    if (data.crawl_health) setCrawlHealth(data.crawl_health);
    api.getCrawlHistory(getClientId()).then((res) => {
      if (res.success && res.data) setCrawlHistory(res.data.history);
    }).catch(() => {});
  }

  async function regenerateDigest() {
    setDigestLoading(true);
    try {
      const res = await api.generateJobDigest(getClientId());
      if (res.success && res.data) setDigest(res.data);
    } finally {
      setDigestLoading(false);
    }
  }

  async function crawl(providers: string[]) {
    setCrawling(true);
    setCrawlReport(copy.crawl.starting);
    setDigestLoading(true);
    setCrawlRunning(copy.crawl.starting);
    try {
      const res = await api.crawlJobs(getClientId(), providers);
      if (!res.success || !res.data) return;
      const data = res.data;
      if (data.status === "running") {
        setCrawlReport(copy.crawl.backgroundHint);
        setCrawlRunning(data.progress || copy.crawl.running);
        return;
      }
      if (data.status === "error") throw new Error(data.error || copy.crawl.failed);
      applyCrawlResult(data);
      const label = providers.includes("university_html") ? "全量" : "快速";
      if (data.new_count != null && data.total != null) {
        const q = data.quality;
        const extra = q?.validated_ok != null ? copy.crawl.doneWithQuality(q.validated_ok) : "";
        setCrawlReport(`${label}：${copy.crawl.doneWithCount(data.new_count, data.total, extra)}`);
      }
      await load();
    } catch (e) {
      setCrawlReport((e as Error).message);
    } finally {
      setCrawling(false);
      setDigestLoading(false);
    }
  }

  async function ingestWechat() {
    if (!wechatUrl.trim()) return;
    await api.ingestWechatJob(getClientId(), wechatUrl.trim());
    setWechatUrl("");
    load();
  }

  function toggle(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  }

  const cityOptions = useMemo(() => {
    const counts = meta?.work_cities || {};
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 12)
      .map(([c]) => c);
  }, [meta]);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return jobs;
    return jobs.filter((j) => {
      const hay = [
        j.company,
        j.role,
        j.job_type,
        j.channel,
        sourceLabel(j),
        positionTitles(j),
        ...(j.tags || []),
        ...workCities(j),
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [jobs, filter]);

  const priorityMap = useMemo(() => {
    const m = new Map<string, string>();
    digest?.priority_jobs?.forEach((p) => m.set(p.job_id, p.priority));
    return m;
  }, [digest]);

  function applyJobById(jobId: string) {
    const job = jobs.find((j) => j.id === jobId);
    if (!job) return;
    api.hub
      .recordBehavior(getClientId(), "tailor_start", {
        job_id: job.id,
        company: job.company,
        role: job.role,
      })
      .catch(() => {});
    api.hub.recordFunnel(getClientId(), "job_tailor_start", { job_id: job.id }).catch(() => {});
    setStudioFromJob(job);
    setJdText(job.jd_text || "");
    router.push(`${ROUTES.studioPrepare}?from=job`);
  }
  function startWithJob(job: JobPosting, e: React.MouseEvent) {
    e.stopPropagation();
    applyJobById(job.id);
  }

  return (
    <main className="page-shell-wide">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <Globe size={22} className="text-[var(--primary)]" /> {copy.jobs.title}
          </h1>
          <p className="page-subtitle">{copy.jobs.subtitle}</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => crawl(["job_aggregator", "company_campus"])}
            disabled={crawling}
            title="牛客日程 + 企业官网，后台运行，可同时进行改稿"
            className="inline-flex items-center gap-2 px-4 py-2 btn-primary"
          >
            {crawling ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            {copy.jobs.refresh}
          </button>
          <button
            type="button"
            onClick={() => crawl(["job_aggregator", "company_campus", "university_html"])}
            disabled={crawling}
            title="含高校就业网，后台运行，可同时进行改稿"
            className="inline-flex items-center gap-2 px-4 py-2 btn-secondary"
          >
            {crawling ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            {copy.jobs.refreshFull}
          </button>
          {selected.size > 0 && (
            <a
              href={`/jobs/compare?ids=${Array.from(selected).join(",")}`}
              className="btn-primary px-4 py-2"
            >
              {copy.jobs.compareSelected} ({selected.size})
            </a>
          )}
        </div>
      </div>

      {meta && (
        <div className="mb-4 flex flex-wrap gap-3 text-xs text-[var(--text-secondary)]">
          <span className="px-2 py-1 surface-card text-xs">共 {meta.total} 条</span>
          <span className="px-2 py-1 surface-card text-xs">已保存到本地岗位库 SQLite</span>
          {meta.last_crawled_at && (
            <span className="px-2 py-1 surface-card text-xs">
              最近抓取 {formatDateShort(meta.last_crawled_at)}
            </span>
          )}
          {Object.entries(meta.job_types)
            .slice(0, 5)
            .map(([k, v]) => (
              <span key={k} className="chip-primary text-xs">
                {k} {v}
              </span>
            ))}
          {crawlHealth?.summary && (
            <span
              className={`px-2 py-1 border rounded-[var(--radius-sm)] text-xs ${
                crawlHealth.summary === "healthy"
                  ? "alert-success"
                  : crawlHealth.summary === "degraded"
                    ? "alert-error"
                    : "alert-warning"
              }`}
            >
              爬虫 {crawlHealth.summary === "healthy" ? "正常" : crawlHealth.summary === "degraded" ? "异常" : "部分可用"}
            </span>
          )}
        </div>
      )}

      {crawlHistory.length > 0 && (
        <div className="mb-4 surface-card p-3">
          <div className="flex items-center justify-between gap-3 mb-2">
            <p className="section-label">爬虫数据存档</p>
            <span className="text-xs text-[var(--text-disabled)]">保留最近 {crawlHistory.length} 次运行</span>
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {crawlHistory.slice(0, 5).map((run) => {
              const providers = Object.entries(run.providers || {});
              const ok = run.summary === "healthy";
              return (
                <div
                  key={run.run_at}
                  className="min-w-[220px] rounded-[var(--radius-md)] border border-[var(--border-subtle)] p-3 bg-[var(--surface-container)]"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className={ok ? "text-[var(--semantic-success)] text-xs" : "text-[var(--semantic-warning)] text-xs"}>
                      {ok ? "抓取正常" : "部分异常"}
                    </span>
                    <span className="text-[11px] text-[var(--text-disabled)]">{formatDateShort(run.run_at)}</span>
                  </div>
                  <p className="text-sm text-[var(--text-primary)] mt-2">
                    新增 {run.new_count} 条 / 当前 {run.total} 条
                  </p>
                  <p className="text-[11px] text-[var(--text-secondary)] mt-1 line-clamp-1">
                    {providers.map(([name, p]) => `${name} ${p.fetched ?? 0}`).join(" · ")}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <JobPreferencesPanel
        onSaved={() => {
          regenerateDigest();
        }}
      />

      <JobDigestPanel
        digest={digest}
        loading={digestLoading}
        onRegenerate={regenerateDigest}
        onApplyJob={applyJobById}
      />

      {crawlReport && (
        <p
          className={
            crawlUiStatus === "running"
              ? "mb-3 text-sm text-[var(--text-secondary)]"
              : "mb-3 text-sm text-[var(--semantic-success)]"
          }
        >
          {crawlReport}
        </p>
      )}

      <div className="mb-3 flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-disabled)]" />
          <input
            className="w-full pl-9 pr-3 py-2 border rounded-lg text-sm"
            placeholder="搜索公司 / 职位 / 城市 / 标签"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        <select
          className="border rounded-lg px-3 py-2 text-sm bg-white"
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
        >
          {SOURCE_OPTIONS.map((o) => (
            <option key={o.id || "all"} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
        <select
          className="border rounded-lg px-3 py-2 text-sm bg-white"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
        >
          <option value="">全部类型</option>
          {TYPE_OPTIONS.filter(Boolean).map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          className="border rounded-lg px-3 py-2 text-sm bg-white"
          value={cityFilter}
          onChange={(e) => setCityFilter(e.target.value)}
        >
          <option value="">全部工作地</option>
          {cityOptions.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <label className="inline-flex items-center gap-1.5 text-sm text-[var(--text-secondary)] px-2">
          <input type="checkbox" checked={hideWeak} onChange={(e) => setHideWeak(e.target.checked)} />
          隐藏资讯/待补全
        </label>
        <div className="flex gap-2 min-w-[240px] flex-1">
          <input
            className="flex-1 border rounded-lg px-3 py-2 text-sm"
            placeholder="粘贴公众号文章链接"
            value={wechatUrl}
            onChange={(e) => setWechatUrl(e.target.value)}
          />
          <button
            type="button"
            onClick={ingestWechat}
            className="px-3 py-2 border rounded-lg text-sm flex items-center gap-1 hover:bg-[var(--surface-base)]"
          >
            <Link2 size={14} /> 订阅
          </button>
        </div>
      </div>

      {loading ? (
        <div className="py-20 text-center text-[var(--text-disabled)]">
          <Loader2 className="animate-spin mx-auto" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="py-16 text-center text-[var(--text-secondary)] surface-card">
          暂无匹配岗位。可放宽筛选，或点击「刷新岗位」重新抓取。
        </div>
      ) : (
        <div className="surface-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--surface-base)] text-[var(--text-secondary)] text-xs">
                <tr>
                  <th className="w-8 px-3 py-2" />
                  <th className="text-left px-3 py-2 font-medium min-w-[100px]">用人单位</th>
                  <th className="text-left px-3 py-2 font-medium min-w-[140px]">职位/批次</th>
                  <th className="text-left px-3 py-2 font-medium w-16">类型</th>
                  <th className="text-left px-3 py-2 font-medium min-w-[80px]">工作地</th>
                  <th className="text-left px-3 py-2 font-medium w-20">收录</th>
                  <th className="text-left px-3 py-2 font-medium w-20">截止</th>
                  <th className="text-left px-3 py-2 font-medium w-28">发布渠道</th>
                  <th className="text-right px-3 py-2 font-medium w-36">操作</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((job) => {
                  const cities = workCities(job);
                  const positions = positionTitles(job);
                  const companyText = displayCompany(job);
                  const roleText = displayRole(job);
                  return (
                    <tr
                      key={job.id}
                      className={`border-t hover:bg-[var(--surface-base)]/80 ${selected.has(job.id) ? "bg-[var(--primary-muted)]" : ""}`}
                    >
                      <td className="px-3 py-2 align-top">
                        <input
                          type="checkbox"
                          checked={selected.has(job.id)}
                          onChange={() => toggle(job.id)}
                          aria-label="对比"
                        />
                      </td>
                      <td className="px-3 py-2 align-top">
                        <div className="font-semibold text-[var(--text-primary)] leading-snug flex items-center gap-1.5 flex-wrap">
                          {priorityMap.get(job.id) && (
                            <span
                              className={`text-[10px] px-1 py-0.5 rounded font-bold ${
                                PRIORITY_BADGE[priorityMap.get(job.id)!] || PRIORITY_BADGE.P2
                              }`}
                            >
                              {priorityMap.get(job.id)}
                            </span>
                          )}
                          {job.jd_url ? (
                            <a
                              href={job.jd_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="hover:text-[var(--primary)] hover:underline"
                              title="打开原始岗位链接"
                            >
                              {companyText}
                            </a>
                          ) : (
                            companyText
                          )}
                          {job.legitimacy === "trusted" && (
                            <span
                              title="来自官方招聘系统 / 社区维护校招库，真实性高"
                              className="text-[10px] px-1 py-0.5 rounded font-medium bg-[var(--semantic-success-muted)] text-[var(--semantic-success)]"
                            >
                              可信
                            </span>
                          )}
                          {job.legitimacy === "suspect" && (
                            <span
                              title="来源未经核实，投递前请确认企业真实性"
                              className="text-[10px] px-1 py-0.5 rounded font-medium bg-[var(--semantic-warning-muted)] text-[var(--semantic-warning)]"
                            >
                              待核实
                            </span>
                          )}
                        </div>
                        {companyText === "—" && job.source === "university_html" && (
                          <div className="text-[11px] text-[var(--text-disabled)] mt-0.5">用人单位待解析</div>
                        )}
                        {facetTags(job).slice(0, 2).map((t) => (
                          <span
                            key={t}
                            className="inline-block mt-1 mr-1 text-[10px] px-1.5 py-0.5 bg-[var(--surface-base)] text-[var(--text-secondary)] rounded"
                          >
                            {t}
                          </span>
                        ))}
                      </td>
                      <td className="px-3 py-2 align-top">
                        <div className="text-[var(--primary)] font-medium">
                          {job.jd_url ? (
                            <a
                              href={job.jd_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="hover:underline"
                              title="打开原始岗位链接"
                            >
                              {roleText}
                            </a>
                          ) : (
                            roleText
                          )}
                        </div>
                        {positions && (
                          <div className="text-xs text-[var(--text-secondary)] mt-0.5 line-clamp-2" title={positions}>
                            {positions}
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-2 align-top text-[var(--text-primary)]">{job.job_type || "校招"}</td>
                      <td className="px-3 py-2 align-top text-[var(--text-primary)]">
                        {cities.length ? cities.join("、") : "—"}
                      </td>
                      <td className="px-3 py-2 align-top text-[var(--text-secondary)] whitespace-nowrap">
                        {freshnessLabel(job)}
                      </td>
                      <td className="px-3 py-2 align-top text-[var(--text-secondary)] whitespace-nowrap">
                        {job.deadline ? formatDateShort(job.deadline) : "—"}
                      </td>
                      <td className="px-3 py-2 align-top">
                        <span className="text-xs text-[var(--text-primary)]">{publisherLabel(job)}</span>
                        <div className="text-[10px] text-[var(--text-disabled)] mt-0.5">{sourceLabel(job)}</div>
                        {job.validation_status === "weak" && (
                          <div className="text-[10px] text-[var(--semantic-warning)] mt-0.5">待补全</div>
                        )}
                      </td>
                      <td className="px-3 py-2 align-top text-right whitespace-nowrap">
                        <div className="flex flex-col items-end gap-1">
                          {job.jd_url && (
                            <a
                              href={job.jd_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-xs text-[var(--primary)] hover:underline"
                            >
                              <ExternalLink size={12} /> 原文
                            </a>
                          )}
                          {job.referral_code && (
                            <span
                              title="内推码（投递时填写可加速）"
                              className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--primary-muted)] text-[var(--primary)] font-mono"
                            >
                              内推 {job.referral_code}
                            </span>
                          )}
                          <button
                            type="button"
                            onClick={(e) => startWithJob(job, e)}
                            className="inline-flex items-center gap-1 px-2 py-1 text-xs btn-primary"
                          >
                            <Sparkles size={12} /> 改简历
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <CareerCopilotPanel
        onApplyJob={applyJobById}
        onCrawl={() => crawl(["job_aggregator", "company_campus"])}
        onFilter={(q) => setFilter(q)}
        onCompare={(ids) => router.push(`/jobs/compare?ids=${ids.join(",")}`)}
      />
    </main>
  );
}

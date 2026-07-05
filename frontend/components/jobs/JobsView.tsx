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
  attestationSummary,
  cohortLabel,
  positionTitles,
  publisherLabel,
  sourceLabel,
  workCities,
} from "@/lib/jobDisplay";
import {
  ChevronDown,
  ExternalLink,
  Globe,
  Link2,
  Loader2,
  PenLine,
  RefreshCw,
  Search,
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

const TYPE_OPTIONS = ["", "实习", "校招", "提前批", "秋招", "春招", "补录"];

const SOURCE_OPTIONS = [
  { id: "", label: "全部来源" },
  { id: "github_joblist", label: "GitHub 校招库" },
  { id: "browser_discovery", label: "浏览器检索" },
  { id: "early_batch", label: "27届提前批" },
  { id: "search_discovery", label: "AI 搜索发现" },
  { id: "campus_patrol", label: "大厂巡检" },
  { id: "job_aggregator", label: "求职平台" },
  { id: "company_campus", label: "企业官网" },
  { id: "university_html", label: "高校就业网" },
  { id: "wechat_discovery", label: "公众号挖掘" },
  { id: "wechat_article", label: "公众号" },
];

const COHORT_OPTIONS = ["", "27届", "26届", "25届"];

function sourceHealthLabel(summary?: string) {
  if (summary === "healthy") return copy.jobs.sourceHealthy;
  if (summary === "degraded") return copy.jobs.sourceDegraded;
  return copy.jobs.sourcePartial;
}

export default function JobsView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setStudioFromJob, setJdText, pushToast } = useAppStore();
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
  const [cohortFilter, setCohortFilter] = useState("27届");
  const [includeUnknownCohort, setIncludeUnknownCohort] = useState(true);
  const [hideWeak, setHideWeak] = useState(true);
  const [digest, setDigest] = useState<JobDigest | null>(null);
  const [digestLoading, setDigestLoading] = useState(false);
  const [crawlHealth, setCrawlHealth] = useState<CrawlHealth | null>(null);
  const [crawlHistory, setCrawlHistory] = useState<CrawlRun[]>([]);

  const crawlUiStatus = useCrawlStore((s) => s.status);
  const crawlProgress = useCrawlStore((s) => s.progress);
  const partialTotal = useCrawlStore((s) => s.partialTotal);
  const providerIndex = useCrawlStore((s) => s.providerIndex);
  const providerTotal = useCrawlStore((s) => s.providerTotal);
  const lastResult = useCrawlStore((s) => s.lastResult);
  const setCrawlRunning = useCrawlStore((s) => s.setRunning);
  const consumeLastResult = useCrawlStore((s) => s.consumeLastResult);

  useEffect(() => {
    const q = searchParams.get("filter");
    if (q) setFilter(q);
  }, [searchParams]);

  async function load(options?: { silent?: boolean }) {
    if (!options?.silent) setLoading(true);
    try {
      const res = await api.getJobFeed(getClientId(), {
        source: sourceFilter || undefined,
        job_type: typeFilter || undefined,
        work_city: cityFilter || undefined,
        graduation_cohort: cohortFilter || undefined,
        include_unknown_cohort: includeUnknownCohort,
        include_weak: !hideWeak,
      });
      if (res.success && res.data) {
        setJobs(res.data.jobs);
        setMeta(res.data.meta || null);
        if (res.data.digest) setDigest(res.data.digest);
      }
    } finally {
      if (!options?.silent) setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [sourceFilter, typeFilter, cityFilter, cohortFilter, includeUnknownCohort, hideWeak]);

  useEffect(() => {
    api.getCrawlHealth(getClientId()).then((res) => {
      if (res.success && res.data) setCrawlHealth(res.data);
    }).catch(() => {});
    api.getCrawlHistory(getClientId()).then((res) => {
      if (res.success && res.data) setCrawlHistory(res.data.history);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!lastResult) return;
    applyCrawlResult(lastResult);
    consumeLastResult();
    void load();
  }, [lastResult, consumeLastResult]);

  useEffect(() => {
    if (crawlUiStatus !== "running") return;
    const timer = window.setInterval(() => {
      void load({ silent: true });
    }, 3000);
    return () => window.clearInterval(timer);
  }, [crawlUiStatus, sourceFilter, typeFilter, cityFilter, cohortFilter, includeUnknownCohort, hideWeak]);

  function notifyCrawl(message: string, type: "info" | "success" | "error" | "warning" = "success") {
    if (!message) return;
    pushToast(message, type, 5000);
  }

  function applyCrawlResult(data: {
    new_count?: number;
    total?: number;
    quality?: { validated_ok?: number };
    cross_verify?: { cross_verified?: number };
    organize?: { before?: number; after?: number; ok_count?: number; actionable?: number; cross_verified?: number };
    jobs?: JobPosting[];
    digest?: JobDigest;
    crawl_health?: CrawlHealth;
  }) {
    if (data.jobs) setJobs(data.jobs);
    if (data.digest) setDigest(data.digest);
    const q = data.quality;
    const qualityLine = q ? copy.crawl.doneWithQuality(q.validated_ok ?? 0) : "";
    if (data.new_count != null && data.total != null) {
      let msg = copy.crawl.doneWithCount(data.new_count, data.total, qualityLine);
      const org = data.organize;
      if (org?.actionable != null) {
        msg += `，整理后 ${org.actionable} 条可浏览`;
      }
      const cv = data.cross_verify?.cross_verified ?? org?.cross_verified;
      if (cv != null && cv > 0) {
        msg += `，${copy.jobs.crossVerified(cv)}`;
      }
      notifyCrawl(msg, "success");
    } else if (data.organize?.before != null && data.organize?.after != null) {
      notifyCrawl(
        copy.jobs.organizeDone(
          data.organize.before,
          data.organize.after,
          data.organize.ok_count ?? data.organize.actionable ?? 0
        ),
        "success"
      );
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

  async function refreshJobs() {
    if (crawling || crawlUiStatus === "running") return;
    setCrawling(true);
    setDigestLoading(true);
    setCrawlRunning(copy.crawl.starting);
    try {
      const res = await api.crawlJobs(getClientId(), null);
      if (!res.success || !res.data) return;
      const data = res.data;
      if (data.status === "running") {
        notifyCrawl(copy.jobs.refreshHint, "info");
        setCrawlRunning(data.progress || copy.crawl.running);
        return;
      }
      if (data.status === "error") throw new Error(data.error || copy.crawl.failed);
      applyCrawlResult(data);
      await load();
    } catch (e) {
      notifyCrawl((e as Error).message || copy.crawl.failed, "error");
    } finally {
      setCrawling(false);
      setDigestLoading(false);
    }
  }

  async function ingestWechat() {
    if (!wechatUrl.trim()) return;
    await api.ingestWechatJob(getClientId(), wechatUrl.trim());
    setWechatUrl("");
    pushToast("已添加公众号岗位", "success");
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

  function startWithJob(job: JobPosting, e?: React.MouseEvent) {
    e?.stopPropagation();
    applyJobById(job.id);
  }

  function relaxFilters() {
    setFilter("");
    setSourceFilter("");
    setTypeFilter("");
    setCityFilter("");
    setCohortFilter("");
    setIncludeUnknownCohort(true);
    setHideWeak(false);
  }

  return (
    <main className="page-shell-wide">
      <div className="flex flex-wrap items-start justify-between gap-4 mb-5">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <Globe size={22} className="text-[var(--primary)]" /> {copy.jobs.title}
          </h1>
          <p className="page-subtitle">{copy.jobs.subtitle}</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            type="button"
            onClick={refreshJobs}
            disabled={crawling || crawlUiStatus === "running"}
            title={copy.jobs.refreshHint}
            className="inline-flex items-center gap-2 px-4 py-2 btn-primary"
          >
            {crawling || crawlUiStatus === "running" ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <RefreshCw size={14} />
            )}
            {copy.jobs.refresh}
          </button>
          {selected.size > 0 && (
            <a
              href={`/jobs/compare?ids=${Array.from(selected).join(",")}`}
              className="btn-secondary px-4 py-2"
            >
              {copy.jobs.compareSelected} ({selected.size})
            </a>
          )}
        </div>
      </div>

      {crawlUiStatus === "running" && (
        <div
          className="mb-4 flex items-center gap-3 rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--surface-base)] px-4 py-3 text-sm text-[var(--text-secondary)]"
          role="status"
          aria-live="polite"
        >
          <Loader2 size={16} className="animate-spin shrink-0 text-[var(--primary)]" />
          <div className="min-w-0">
            <p className="text-[var(--text-primary)] truncate">
              {crawlProgress || copy.crawl.running}
            </p>
            <p className="text-xs text-[var(--text-disabled)] mt-0.5">
              {providerTotal > 0
                ? copy.crawl.runningDetail(providerIndex, providerTotal, partialTotal || meta?.total || 0)
                : copy.jobs.refreshHint}
            </p>
          </div>
        </div>
      )}

      <div className="relative mb-4">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-disabled)]" />
        <input
          className="input-field pl-10"
          placeholder={copy.jobs.searchPlaceholder}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>

      <div className="mb-4 flex flex-wrap gap-2 items-center">
        <select className="input-select" value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}>
          {SOURCE_OPTIONS.map((o) => (
            <option key={o.id || "all"} value={o.id}>{o.label}</option>
          ))}
        </select>
        <select className="input-select" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">全部类型</option>
          {TYPE_OPTIONS.filter(Boolean).map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select className="input-select" value={cityFilter} onChange={(e) => setCityFilter(e.target.value)}>
          <option value="">全部工作地</option>
          {cityOptions.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select className="input-select" value={cohortFilter} onChange={(e) => setCohortFilter(e.target.value)}>
          <option value="">{copy.jobs.cohortAll}</option>
          {COHORT_OPTIONS.filter(Boolean).map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        {cohortFilter && (
          <label className="inline-flex items-center gap-1.5 text-sm text-[var(--text-secondary)] cursor-pointer">
            <input
              type="checkbox"
              checked={includeUnknownCohort}
              onChange={(e) => setIncludeUnknownCohort(e.target.checked)}
            />
            {copy.jobs.includeUnknownCohort}
          </label>
        )}
        <label className="inline-flex items-center gap-1.5 text-sm text-[var(--text-secondary)] cursor-pointer">
          <input type="checkbox" checked={hideWeak} onChange={(e) => setHideWeak(e.target.checked)} />
          {copy.jobs.hideWeakLabel}
        </label>
      </div>

      {meta && (
        <p className="mb-4 text-xs text-[var(--text-secondary)]">
          共 {meta.total} 条 · {copy.jobs.syncedLocal}
          {meta.cross_verified_count != null && meta.cross_verified_count > 0 && (
            <span className=" text-[var(--primary)]"> · {copy.jobs.crossVerified(meta.cross_verified_count)}</span>
          )}
          {meta.last_crawled_at && ` · 更新于 ${formatDateShort(meta.last_crawled_at)}`}
          {crawlHealth?.summary && (
            <span
              className={
                crawlHealth.summary === "healthy"
                  ? " text-[var(--semantic-success)]"
                  : crawlHealth.summary === "degraded"
                    ? " text-[var(--semantic-danger)]"
                    : " text-[var(--semantic-warning)]"
              }
            >
              {" "}· {sourceHealthLabel(crawlHealth.summary)}
            </span>
          )}
        </p>
      )}

      {loading ? (
        <div className="py-20 text-center text-[var(--text-disabled)]">
          <Loader2 className="animate-spin mx-auto" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="py-14 px-6 text-center surface-card">
          <p className="text-base font-medium text-[var(--text-primary)] mb-1">{copy.jobs.emptyTitle}</p>
          <p className="text-sm text-[var(--text-secondary)] mb-5">{copy.jobs.emptyHint}</p>
          <div className="flex flex-wrap justify-center gap-2">
            <button
              type="button"
              onClick={refreshJobs}
              disabled={crawling || crawlUiStatus === "running"}
              className="btn-primary"
            >
              {copy.jobs.refresh}
            </button>
            <button type="button" onClick={relaxFilters} className="btn-secondary">
              放宽筛选
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="md:hidden space-y-3 mb-6">
            {filtered.map((job) => (
              <JobMobileCard
                key={job.id}
                job={job}
                priority={priorityMap.get(job.id)}
                selected={selected.has(job.id)}
                onToggle={() => toggle(job.id)}
                onTailor={() => startWithJob(job)}
              />
            ))}
          </div>

          <div className="hidden md:block surface-card overflow-hidden">
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
                  {filtered.map((job) => (
                    <JobTableRow
                      key={job.id}
                      job={job}
                      priority={priorityMap.get(job.id)}
                      selected={selected.has(job.id)}
                      onToggle={() => toggle(job.id)}
                      onTailor={(e) => startWithJob(job, e)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      <details className="mt-8 surface-card group">
        <summary className="flex items-center justify-between gap-3 p-4 cursor-pointer list-none [&::-webkit-details-marker]:hidden">
          <span className="text-sm font-medium text-[var(--text-primary)]">{copy.jobs.advanced}</span>
          <ChevronDown size={16} className="text-[var(--text-secondary)] group-open:rotate-180 transition-transform" />
        </summary>
        <div className="px-4 pb-4 space-y-4 border-t border-[var(--border-faint)]">
          <JobPreferencesPanel onSaved={() => regenerateDigest()} />

          <JobDigestPanel
            digest={digest}
            loading={digestLoading}
            onRegenerate={regenerateDigest}
            onApplyJob={applyJobById}
          />

          {crawlHistory.length > 0 && (
            <div>
              <p className="section-label mb-2">{copy.jobs.updateHistory}</p>
              <div className="flex gap-2 overflow-x-auto pb-1">
                {crawlHistory.slice(0, 5).map((run) => {
                  const ok = run.summary === "healthy";
                  return (
                    <div
                      key={run.run_at}
                      className="min-w-[200px] rounded-[var(--radius-md)] border border-[var(--border-subtle)] p-3 bg-[var(--surface-base)]"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className={ok ? "text-[var(--semantic-success)] text-xs" : "text-[var(--semantic-warning)] text-xs"}>
                          {ok ? copy.jobs.sourceHealthy : copy.jobs.sourcePartial}
                        </span>
                        <span className="text-xs text-[var(--text-disabled)]">{formatDateShort(run.run_at)}</span>
                      </div>
                      <p className="text-sm text-[var(--text-primary)] mt-2">
                        新增 {run.new_count} 条 · 共 {run.total} 条
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-2 items-center">
            <input
              className="input-field flex-1 min-w-[200px]"
              placeholder="粘贴公众号文章链接"
              value={wechatUrl}
              onChange={(e) => setWechatUrl(e.target.value)}
            />
            <button type="button" onClick={ingestWechat} className="btn-secondary text-sm">
              <Link2 size={14} /> 添加
            </button>
          </div>
        </div>
      </details>

      <CareerCopilotPanel
        onApplyJob={applyJobById}
        onCrawl={refreshJobs}
        onFilter={(q) => setFilter(q)}
        onCompare={(ids) => router.push(`/jobs/compare?ids=${ids.join(",")}`)}
      />
    </main>
  );
}

function JobTableRow({
  job,
  priority,
  selected,
  onToggle,
  onTailor,
}: {
  job: JobPosting;
  priority?: string;
  selected: boolean;
  onToggle: () => void;
  onTailor: (e: React.MouseEvent) => void;
}) {
  const cities = workCities(job);
  const positions = positionTitles(job);
  const companyText = displayCompany(job);
  const roleText = displayRole(job);

  return (
    <tr className={`border-t hover:bg-[var(--surface-base)]/80 ${selected ? "bg-[var(--primary-muted)]" : ""}`}>
      <td className="px-3 py-2 align-top">
        <input type="checkbox" checked={selected} onChange={onToggle} aria-label="对比" />
      </td>
      <td className="px-3 py-2 align-top">
        <div className="font-semibold text-[var(--text-primary)] leading-snug flex items-center gap-1.5 flex-wrap">
          {priority && (
            <span className={`text-xs px-1 py-0.5 rounded font-bold ${PRIORITY_BADGE[priority] || PRIORITY_BADGE.P2}`}>
              {priority}
            </span>
          )}
          {job.jd_url ? (
            <a href={job.jd_url} target="_blank" rel="noopener noreferrer" className="hover:text-[var(--primary)] hover:underline">
              {companyText}
            </a>
          ) : (
            companyText
          )}
          {job.legitimacy === "trusted" && (
            <span className="text-xs px-1 py-0.5 rounded font-medium bg-[var(--semantic-success-muted)] text-[var(--semantic-success)]">可信</span>
          )}
          {job.cross_verified && (
            <span className="text-xs px-1 py-0.5 rounded font-medium bg-[var(--semantic-success-muted)] text-[var(--semantic-success)]">
              {copy.jobs.crossVerifiedBadge}
              {job.verification_source_count ? ` · ${job.verification_source_count}` : ""}
            </span>
          )}
          {cohortLabel(job) ? (
            <span className="text-xs px-1 py-0.5 rounded font-medium bg-[var(--primary-muted)] text-[var(--primary)]">
              {cohortLabel(job)}
            </span>
          ) : (
            <span className="text-xs px-1 py-0.5 rounded font-medium bg-[var(--surface-base)] text-[var(--text-disabled)]">
              届别待确认
            </span>
          )}
        </div>
        {facetTags(job).slice(0, 2).map((t) => (
          <span key={t} className="inline-block mt-1 mr-1 text-xs px-1.5 py-0.5 bg-[var(--surface-base)] text-[var(--text-secondary)] rounded-[var(--radius-sm)]">
            {t}
          </span>
        ))}
      </td>
      <td className="px-3 py-2 align-top">
        <div className="text-[var(--primary)] font-medium">
          {job.jd_url ? (
            <a href={job.jd_url} target="_blank" rel="noopener noreferrer" className="hover:underline">{roleText}</a>
          ) : (
            roleText
          )}
        </div>
        {positions && <div className="text-xs text-[var(--text-secondary)] mt-0.5 line-clamp-2">{positions}</div>}
        {attestationSummary(job) && (
          <div className="text-xs text-[var(--text-disabled)] mt-0.5">来源：{attestationSummary(job)}</div>
        )}
      </td>
      <td className="px-3 py-2 align-top">{job.job_type || "校招"}</td>
      <td className="px-3 py-2 align-top">{cities.length ? cities.join("、") : "—"}</td>
      <td className="px-3 py-2 align-top text-[var(--text-secondary)] whitespace-nowrap">{freshnessLabel(job)}</td>
      <td className="px-3 py-2 align-top text-[var(--text-secondary)] whitespace-nowrap">
        {job.deadline ? formatDateShort(job.deadline) : "—"}
      </td>
      <td className="px-3 py-2 align-top">
        <span className="text-xs">{publisherLabel(job)}</span>
        <div className="text-xs text-[var(--text-disabled)] mt-0.5">{sourceLabel(job)}</div>
      </td>
      <td className="px-3 py-2 align-top text-right whitespace-nowrap">
        <div className="flex flex-col items-end gap-1">
          {job.jd_url && (
            <a href={job.jd_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-[var(--primary)] hover:underline">
              <ExternalLink size={12} /> 原文
            </a>
          )}
          <button type="button" onClick={onTailor} className="inline-flex items-center gap-1 px-2 py-1 text-xs btn-primary">
            <PenLine size={12} /> 改简历
          </button>
        </div>
      </td>
    </tr>
  );
}

function JobMobileCard({
  job,
  priority,
  selected,
  onToggle,
  onTailor,
}: {
  job: JobPosting;
  priority?: string;
  selected: boolean;
  onToggle: () => void;
  onTailor: () => void;
}) {
  const companyText = displayCompany(job);
  const roleText = displayRole(job);
  const cities = workCities(job);

  return (
    <div className={`surface-card p-4 ${selected ? "ring-2 ring-[var(--primary)]/30" : ""}`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            {priority && (
              <span className={`text-xs px-1 py-0.5 rounded font-bold ${PRIORITY_BADGE[priority] || PRIORITY_BADGE.P2}`}>
                {priority}
              </span>
            )}
            <span className="font-medium text-[var(--text-primary)] truncate">{companyText}</span>
          </div>
          <p className="text-sm text-[var(--primary)] mt-0.5">{roleText}</p>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            {[job.job_type || "校招", cities.join("、")].filter(Boolean).join(" · ")}
          </p>
        </div>
        <input type="checkbox" checked={selected} onChange={onToggle} aria-label="对比" className="mt-1" />
      </div>
      <div className="flex items-center gap-2 mt-3">
        {job.jd_url && (
          <a href={job.jd_url} target="_blank" rel="noopener noreferrer" className="btn-secondary text-xs py-1.5 flex-1 justify-center">
            <ExternalLink size={12} /> 原文
          </a>
        )}
        <button type="button" onClick={onTailor} className="btn-primary text-xs py-1.5 flex-1 justify-center">
          <PenLine size={12} /> 改简历
        </button>
      </div>
    </div>
  );
}

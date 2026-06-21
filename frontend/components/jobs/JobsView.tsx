"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import { ROUTES } from "@/lib/navigation";
import { useAppStore } from "@/stores/useAppStore";
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
import type { CrawlHealth } from "@/lib/types";

const PRIORITY_BADGE: Record<string, string> = {
  P0: "bg-red-100 text-red-700",
  P1: "bg-amber-100 text-amber-800",
  P2: "bg-slate-100 text-slate-600",
};

const SOURCE_OPTIONS = [
  { id: "", label: "全部来源" },
  { id: "feishu_bitable", label: "飞书秋招表" },
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
  const [syncingFeishu, setSyncingFeishu] = useState(false);
  const [feishuReady, setFeishuReady] = useState<boolean | null>(null);
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
    api.getFeishuJobStatus().then((res) => {
      if (res.success && res.data) setFeishuReady(res.data.configured);
    }).catch(() => setFeishuReady(false));
    api.getCrawlHealth(getClientId()).then((res) => {
      if (res.success && res.data) setCrawlHealth(res.data);
    }).catch(() => {});
    // 清理历史脏数据（高校资讯误当岗位）
    api.dedupeJobFeed(getClientId()).then((res) => {
      if (res.success && res.data && res.data.before !== res.data.after) load();
    }).catch(() => {});
  }, []);

  async function regenerateDigest() {
    setDigestLoading(true);
    try {
      const res = await api.generateJobDigest(getClientId());
      if (res.success && res.data) setDigest(res.data);
    } finally {
      setDigestLoading(false);
    }
  }

  async function syncFeishu() {
    setSyncingFeishu(true);
    setCrawlReport("");
    setDigestLoading(true);
    try {
      const res = await api.syncFeishuJobs(getClientId());
      if (res.success && res.data) {
        setJobs(res.data.jobs);
        if (res.data.digest) setDigest(res.data.digest);
        const q = res.data.quality;
        const qualityLine = q ? `，其中 ${q.validated_ok ?? 0} 条可投递` : "";
        setCrawlReport(`飞书秋招表已同步 ${res.data.new_count} 条，当前共 ${res.data.total} 条${qualityLine}`);
        await load();
      }
    } catch (e) {
      setCrawlReport(e instanceof Error ? e.message : "飞书同步失败");
    } finally {
      setSyncingFeishu(false);
      setDigestLoading(false);
    }
  }

  async function crawl() {
    setCrawling(true);
    setCrawlReport("");
    setDigestLoading(true);
    try {
      const res = await api.crawlJobs(getClientId());
      if (res.success && res.data) {
        setJobs(res.data.jobs);
        if (res.data.digest) setDigest(res.data.digest);
        const q = res.data.quality;
        const qualityLine = q ? `，其中 ${q.validated_ok ?? 0} 条可投递` : "";
        setCrawlReport(`已更新 ${res.data.new_count} 条，当前共 ${res.data.total} 条${qualityLine}`);
        if ((res.data as { crawl_health?: CrawlHealth }).crawl_health) {
          setCrawlHealth((res.data as { crawl_health?: CrawlHealth }).crawl_health!);
        }
        await load();
      }
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
    setStudioFromJob(job);
    setJdText(job.jd_text || "");
    router.push(`${ROUTES.studioPrepare}?from=job`);
  }
  function startWithJob(job: JobPosting, e: React.MouseEvent) {
    e.stopPropagation();
    applyJobById(job.id);
  }

  return (
    <main className="max-w-7xl mx-auto px-6 py-8">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Globe size={22} /> 岗位发现
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            公司 / 职位 / 工作地 / 收录时间 · 高校来源会标注发布方
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            type="button"
            onClick={syncFeishu}
            disabled={syncingFeishu || feishuReady === false}
            title={
              feishuReady === false
                ? "请先在 backend/.env 配置 FEISHU_APP_ID + FEISHU_APP_SECRET"
                : "从飞书多维表格同步秋招岗位"
            }
            className="inline-flex items-center gap-2 px-3 py-2 border border-emerald-200 text-emerald-700 bg-emerald-50 rounded-lg text-sm disabled:opacity-50 hover:bg-emerald-100"
          >
            {syncingFeishu ? <Loader2 size={14} className="animate-spin" /> : <Link2 size={14} />}
            同步飞书秋招表
          </button>
          <button
            type="button"
            onClick={crawl}
            disabled={crawling}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm"
          >
            {crawling ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            刷新岗位
          </button>
          {selected.size > 0 && (
            <a
              href={`/jobs/compare?ids=${Array.from(selected).join(",")}`}
              className="px-4 py-2 bg-violet-600 text-white rounded-lg text-sm"
            >
              对比 {selected.size} 个
            </a>
          )}
        </div>
      </div>

      {meta && (
        <div className="mb-4 flex flex-wrap gap-3 text-xs text-slate-600">
          <span className="px-2 py-1 bg-white border rounded-md">共 {meta.total} 条</span>
          {meta.last_crawled_at && (
            <span className="px-2 py-1 bg-white border rounded-md">
              最近抓取 {formatDateShort(meta.last_crawled_at)}
            </span>
          )}
          {Object.entries(meta.job_types)
            .slice(0, 5)
            .map(([k, v]) => (
              <span key={k} className="px-2 py-1 bg-blue-50 text-blue-700 border border-blue-100 rounded-md">
                {k} {v}
              </span>
            ))}
          {crawlHealth?.summary && (
            <span
              className={`px-2 py-1 border rounded-md ${
                crawlHealth.summary === "healthy"
                  ? "bg-emerald-50 text-emerald-700 border-emerald-100"
                  : crawlHealth.summary === "degraded"
                    ? "bg-red-50 text-red-700 border-red-100"
                    : "bg-amber-50 text-amber-800 border-amber-100"
              }`}
            >
              爬虫 {crawlHealth.summary === "healthy" ? "正常" : crawlHealth.summary === "degraded" ? "异常" : "部分可用"}
            </span>
          )}
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
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-900">
          {crawlReport}
        </div>
      )}

      <div className="mb-3 flex flex-wrap gap-2 items-center">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
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
        <label className="inline-flex items-center gap-1.5 text-sm text-slate-600 px-2">
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
            className="px-3 py-2 border rounded-lg text-sm flex items-center gap-1 hover:bg-slate-50"
          >
            <Link2 size={14} /> 订阅
          </button>
        </div>
      </div>

      {loading ? (
        <div className="py-20 text-center text-slate-400">
          <Loader2 className="animate-spin mx-auto" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="py-16 text-center text-slate-500 bg-white border rounded-xl">
          暂无匹配岗位。可放宽筛选，或点击「刷新岗位」重新抓取。
        </div>
      ) : (
        <div className="bg-white border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600 text-xs">
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
                  return (
                    <tr
                      key={job.id}
                      className={`border-t hover:bg-slate-50/80 ${selected.has(job.id) ? "bg-violet-50/50" : ""}`}
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
                        <div className="font-semibold text-slate-900 leading-snug flex items-center gap-1.5 flex-wrap">
                          {priorityMap.get(job.id) && (
                            <span
                              className={`text-[10px] px-1 py-0.5 rounded font-bold ${
                                PRIORITY_BADGE[priorityMap.get(job.id)!] || PRIORITY_BADGE.P2
                              }`}
                            >
                              {priorityMap.get(job.id)}
                            </span>
                          )}
                          {displayCompany(job)}
                        </div>
                        {displayCompany(job) === "—" && job.source === "university_html" && (
                          <div className="text-[11px] text-slate-400 mt-0.5">用人单位待解析</div>
                        )}
                        {facetTags(job).slice(0, 2).map((t) => (
                          <span
                            key={t}
                            className="inline-block mt-1 mr-1 text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded"
                          >
                            {t}
                          </span>
                        ))}
                      </td>
                      <td className="px-3 py-2 align-top">
                        <div className="text-blue-700 font-medium">{displayRole(job)}</div>
                        {positions && (
                          <div className="text-xs text-slate-500 mt-0.5 line-clamp-2" title={positions}>
                            {positions}
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-2 align-top text-slate-700">{job.job_type || "校招"}</td>
                      <td className="px-3 py-2 align-top text-slate-700">
                        {cities.length ? cities.join("、") : "—"}
                      </td>
                      <td className="px-3 py-2 align-top text-slate-600 whitespace-nowrap">
                        {freshnessLabel(job)}
                      </td>
                      <td className="px-3 py-2 align-top text-slate-600 whitespace-nowrap">
                        {job.deadline ? formatDateShort(job.deadline) : "—"}
                      </td>
                      <td className="px-3 py-2 align-top">
                        <span className="text-xs text-slate-700">{publisherLabel(job)}</span>
                        <div className="text-[10px] text-slate-400 mt-0.5">{sourceLabel(job)}</div>
                        {job.validation_status === "weak" && (
                          <div className="text-[10px] text-amber-700 mt-0.5">待补全</div>
                        )}
                      </td>
                      <td className="px-3 py-2 align-top text-right whitespace-nowrap">
                        <div className="flex flex-col items-end gap-1">
                          {job.jd_url && (
                            <a
                              href={job.jd_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
                            >
                              <ExternalLink size={12} /> 官方
                            </a>
                          )}
                          <button
                            type="button"
                            onClick={(e) => startWithJob(job, e)}
                            className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-[var(--primary)] text-white rounded-md hover:opacity-90"
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
        onCrawl={crawl}
        onSyncFeishu={syncFeishu}
        onFilter={(q) => setFilter(q)}
        onCompare={(ids) => router.push(`/jobs/compare?ids=${ids.join(",")}`)}
      />
    </main>
  );
}

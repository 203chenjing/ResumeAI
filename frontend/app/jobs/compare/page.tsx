"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import Header from "@/components/layout/Header";
import MatchRadar from "@/components/match/MatchRadar";
import ApplicationDecisionCard from "@/components/match/ApplicationDecision";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import { ROUTES } from "@/lib/navigation";
import { useAppStore } from "@/stores/useAppStore";
import type { CompareRow, JobPosting } from "@/lib/types";
import { ArrowLeft, Loader2, Sparkles } from "lucide-react";

function CompareContent() {
  const router = useRouter();
  const params = useSearchParams();
  const { setStudioFromJob, setJdText } = useAppStore();
  const ids = (params.get("ids") || "").split(",").filter(Boolean);
  const [rows, setRows] = useState<CompareRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState(0);
  const [jobs, setJobs] = useState<JobPosting[]>([]);

  useEffect(() => {
    if (!ids.length) {
      setLoading(false);
      return;
    }
    Promise.all([
      api.compareJobs(getClientId(), ids),
      api.getJobFeed(getClientId()),
    ]).then(([cmp, feed]) => {
      if (cmp.success && cmp.data) setRows(cmp.data.rows);
      if (feed.success && feed.data) setJobs(feed.data.jobs);
      setLoading(false);
    });
  }, [params]);

  const current = rows[active];

  function startStudio(jobId: string) {
    const job = jobs.find((j) => j.id === jobId);
    if (!job) return;
    setStudioFromJob(job);
    setJdText(job.jd_text || "");
    router.push(`${ROUTES.studioPrepare}?from=job`);
  }

  return (
    <>
      <Header />
      <main className="max-w-6xl mx-auto px-6 py-8">
        <Link href="/jobs" className="text-sm text-blue-600 flex items-center gap-1 mb-4">
          <ArrowLeft size={14} /> 返回岗位列表
        </Link>
        <h1 className="text-2xl font-bold mb-2">多岗位对比矩阵</h1>
        <p className="text-sm text-slate-500 mb-6">
          混合匹配：BM25 ×0.42 + 技能图谱 ×0.33 + Jaccard ×0.25 + 偏好加权
        </p>

        {loading ? (
          <Loader2 className="animate-spin mx-auto text-slate-400" />
        ) : rows.length === 0 ? (
          <p className="text-slate-500">请从岗位页选择至少 2 个岗位进行对比</p>
        ) : (
          <>
            <div className="overflow-x-auto mb-6 bg-white border rounded-xl">
              <table className="w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="p-3 text-left">公司</th>
                    <th className="p-3 text-left">岗位</th>
                    <th className="p-3 text-left">混合分</th>
                    <th className="p-3 text-left">BM25</th>
                    <th className="p-3 text-left">技能</th>
                    <th className="p-3 text-left">决策</th>
                    <th className="p-3" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr
                      key={r.job_id}
                      className={`border-t ${active === i ? "bg-blue-50" : ""}`}
                    >
                      <td className="p-3 font-medium">{r.company}</td>
                      <td className="p-3">{r.role}</td>
                      <td className="p-3 font-bold text-blue-700">{r.decision.match_score}</td>
                      <td className="p-3 text-slate-500">{r.score_breakdown?.bm25 ?? "—"}</td>
                      <td className="p-3 text-slate-500">{r.score_breakdown?.skill ?? "—"}</td>
                      <td className="p-3 text-xs">{r.decision.label}</td>
                      <td className="p-3">
                        <button
                          type="button"
                          onClick={() => setActive(i)}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          详情
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {current && (
              <div className="grid md:grid-cols-2 gap-6">
                <div className="bg-white border rounded-xl p-4">
                  <h2 className="font-semibold mb-3">
                    {current.company} · {current.role}
                  </h2>
                  <MatchRadar
                    dimensions={current.match.dimensions}
                    overallScore={current.match.overall_score}
                  />
                </div>
                <div className="space-y-4">
                  <ApplicationDecisionCard decision={current.decision} />
                  <div className="bg-white border rounded-xl p-4">
                    <h3 className="text-sm font-medium mb-2">主要差距</h3>
                    <ul className="text-sm text-slate-600 space-y-1">
                      {current.decision.top_gaps.map((g) => (
                        <li key={g}>· {g}</li>
                      ))}
                    </ul>
                  </div>
                  <button
                    type="button"
                    onClick={() => startStudio(current.job_id)}
                    className="w-full flex items-center justify-center gap-2 py-2 bg-blue-600 text-white rounded-lg text-sm"
                  >
                    <Sparkles size={14} /> 为此岗位改简历
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </>
  );
}

export default function ComparePage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-slate-400">加载中…</div>}>
      <CompareContent />
    </Suspense>
  );
}

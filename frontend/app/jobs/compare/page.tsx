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
import { copy } from "@/lib/copy";

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
      <main className="page-shell">
        <Link href={ROUTES.jobs} className="text-link flex items-center gap-1 mb-4">
          <ArrowLeft size={14} /> {copy.jobs.compareBack}
        </Link>
        <h1 className="page-title text-2xl mb-2">{copy.jobs.compareTitle}</h1>
        <p className="text-sm text-[var(--text-secondary)] mb-6">{copy.jobs.compareSubtitle}</p>

        {loading ? (
          <Loader2 className="animate-spin mx-auto text-[var(--text-disabled)]" />
        ) : rows.length === 0 ? (
          <p className="text-[var(--text-secondary)]">{copy.jobs.compareNeedTwo}</p>
        ) : (
          <>
            <div className="overflow-x-auto mb-6 surface-card">
              <table className="w-full text-sm">
                <thead className="bg-[var(--surface-base)] text-[var(--text-secondary)]">
                  <tr>
                    <th className="p-3 text-left">公司</th>
                    <th className="p-3 text-left">岗位</th>
                    <th className="p-3 text-left">{copy.jobs.compareOverall}</th>
                    <th className="p-3 text-left">{copy.jobs.compareKeyword}</th>
                    <th className="p-3 text-left">{copy.jobs.compareSkill}</th>
                    <th className="p-3 text-left">{copy.jobs.compareDecision}</th>
                    <th className="p-3" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr
                      key={r.job_id}
                      className={`border-t border-[var(--border-subtle)] ${active === i ? "bg-[var(--primary-muted)]" : ""}`}
                    >
                      <td className="p-3 font-medium text-[var(--text-primary)]">{r.company}</td>
                      <td className="p-3 text-[var(--text-primary)]">{r.role}</td>
                      <td className="p-3 font-bold text-[var(--primary)]">{r.decision.match_score}</td>
                      <td className="p-3 text-[var(--text-secondary)]">{r.score_breakdown?.bm25 ?? "—"}</td>
                      <td className="p-3 text-[var(--text-secondary)]">{r.score_breakdown?.skill ?? "—"}</td>
                      <td className="p-3 text-xs text-[var(--text-secondary)]">{r.decision.label}</td>
                      <td className="p-3">
                        <button
                          type="button"
                          onClick={() => setActive(i)}
                          className="text-xs text-link"
                        >
                          {copy.jobs.compareDetail}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {current && (
              <div className="grid md:grid-cols-2 gap-6">
                <div className="surface-card p-4">
                  <h2 className="font-semibold mb-3 text-[var(--text-primary)]">
                    {current.company} · {current.role}
                  </h2>
                  <MatchRadar
                    dimensions={current.match.dimensions}
                    overallScore={current.match.overall_score}
                  />
                </div>
                <div className="space-y-4">
                  <ApplicationDecisionCard decision={current.decision} />
                  <div className="surface-card p-4">
                    <h3 className="text-sm font-medium mb-2 text-[var(--text-primary)]">
                      {copy.jobs.compareGaps}
                    </h3>
                    <ul className="text-sm text-[var(--text-secondary)] space-y-1">
                      {current.decision.top_gaps.map((g) => (
                        <li key={g}>· {g}</li>
                      ))}
                    </ul>
                  </div>
                  <button
                    type="button"
                    onClick={() => startStudio(current.job_id)}
                    className="w-full btn-primary justify-center py-2.5"
                  >
                    <Sparkles size={14} /> {copy.jobs.compareStartEdit}
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
    <Suspense fallback={<div className="p-8 text-center text-[var(--text-disabled)]">{copy.common.loading}</div>}>
      <CompareContent />
    </Suspense>
  );
}

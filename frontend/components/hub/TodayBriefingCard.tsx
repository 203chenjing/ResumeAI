"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Clock, Sparkles, Target } from "lucide-react";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import { ROUTES } from "@/lib/navigation";
import type { TodayBriefing, TodayPick } from "@/lib/types";
import { copy } from "@/lib/copy";

export default function TodayBriefingCard() {
  const [briefing, setBriefing] = useState<TodayBriefing | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.hub
      .getTodayBriefing(getClientId())
      .then((res) => {
        if (res.success && res.data) setBriefing(res.data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="surface-card p-4 animate-pulse h-32" aria-hidden />
    );
  }
  if (!briefing) return null;

  const hasContent = (briefing.top_picks?.length || 0) > 0 || (briefing.urgent_deadlines?.length || 0) > 0;
  if (!hasContent && !briefing.has_resume) return null;

  return (
    <section className="surface-card p-4 space-y-4 border border-[var(--primary-muted)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[var(--primary)] font-medium">
            <Target size={18} />
            {copy.hub.todayTitle}
          </div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)] mt-1">{briefing.headline}</h2>
          {briefing.personalization_note && (
            <p className="text-xs text-[var(--text-secondary)] mt-1">{briefing.personalization_note}</p>
          )}
        </div>
        <Link href={ROUTES.jobs} className="text-xs text-[var(--primary)] hover:underline shrink-0">
          {copy.hub.viewAllJobs}
        </Link>
      </div>

      {briefing.urgent_deadlines && briefing.urgent_deadlines.length > 0 && (
        <div className="space-y-2">
          <p className="section-label flex items-center gap-1">
            <Clock size={14} /> {copy.hub.deadlineUrgent}
          </p>
          {briefing.urgent_deadlines.map((p) => (
            <PickRow key={p.job_id || p.company} pick={p} urgent />
          ))}
        </div>
      )}

      {briefing.top_picks && briefing.top_picks.length > 0 && (
        <div className="space-y-2">
          <p className="section-label flex items-center gap-1">
            <Sparkles size={14} /> {copy.hub.topPicks}
          </p>
          {briefing.top_picks.map((p) => (
            <PickRow key={p.job_id || `${p.company}-${p.role}`} pick={p} />
          ))}
        </div>
      )}

      {!briefing.has_resume && (
        <p className="text-sm text-[var(--text-secondary)] flex items-center gap-2">
          <AlertTriangle size={14} className="text-[var(--semantic-warning)]" />
          {copy.hub.uploadForPicks}
        </p>
      )}
    </section>
  );
}

function PickRow({ pick, urgent }: { pick: TodayPick; urgent?: boolean }) {
  const score = pick.readiness_score ?? pick.match_score;
  return (
    <div
      className={`flex items-center justify-between gap-3 p-2.5 rounded-lg border text-sm ${
        urgent
          ? "border-[var(--semantic-warning-border)] bg-[var(--semantic-warning-muted)]"
          : "border-[var(--border-subtle)] bg-[var(--surface-container)]"
      }`}
    >
      <div className="min-w-0">
        <div className="font-medium text-[var(--text-primary)] truncate">
          {pick.company} · {pick.role}
        </div>
        {pick.reasons && pick.reasons[0] && (
          <div className="text-xs text-[var(--text-secondary)] truncate mt-0.5">{pick.reasons[0]}</div>
        )}
        {urgent && pick.message && (
          <div className="text-xs text-[var(--semantic-warning)] mt-0.5">{pick.message}</div>
        )}
        {pick.referral_code && (
          <span className="inline-block mt-1 text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--primary-muted)] text-[var(--primary)]">
            内推 {pick.referral_code}
          </span>
        )}
      </div>
      <div className="shrink-0 flex flex-col items-end gap-1">
        {score != null && (
          <span className="text-xs font-bold text-[var(--primary)]" title="投递准备度">
            {score}
          </span>
        )}
        <Link
          href={ROUTES.studioPrepare}
          className="text-xs btn-primary px-2 py-1"
          onClick={() => {
            if (pick.job_id) {
              api.hub.recordBehavior(getClientId(), "tailor_start", {
                job_id: pick.job_id,
                company: pick.company,
                role: pick.role,
              });
            }
          }}
        >
          {copy.hub.tailorCta}
        </Link>
      </div>
    </div>
  );
}

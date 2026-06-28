"use client";

import type { JobDigest } from "@/lib/types";
import { Loader2, Sparkles } from "lucide-react";
import { copy } from "@/lib/copy";

const PRIORITY_STYLE: Record<string, string> = {
  P0: "bg-[var(--semantic-danger-muted)] text-[var(--semantic-danger)] border-[var(--semantic-danger-border)]",
  P1: "bg-[var(--semantic-warning-muted)] text-[var(--semantic-warning)] border-[var(--semantic-warning-border)]",
  P2: "bg-[var(--surface-base)] text-[var(--text-secondary)] border-[var(--border-subtle)]",
};

const PRIORITY_LABEL: Record<string, string> = {
  P0: copy.jobs.priority.P0,
  P1: copy.jobs.priority.P1,
  P2: copy.jobs.priority.P2,
};

export default function JobDigestPanel({
  digest,
  loading,
  onRegenerate,
  onApplyJob,
}: {
  digest: JobDigest | null;
  loading?: boolean;
  onRegenerate?: () => void;
  onApplyJob?: (jobId: string) => void;
}) {
  if (loading) {
    return (
      <div className="mb-4 p-4 bg-[var(--primary-muted)] border border-[var(--border-subtle)] rounded-xl flex items-center gap-2 text-sm text-[var(--primary)]">
        <Loader2 size={16} className="animate-spin" /> {copy.jobs.digestLoading}
      </div>
    );
  }

  if (!digest) {
    return (
      <div className="mb-4 p-4 surface-card text-sm text-[var(--text-secondary)]">
        {copy.jobs.digestEmpty}
        {onRegenerate && (
          <button type="button" onClick={onRegenerate} className="ml-2 text-link">
            {copy.jobs.digestRegenerate}
          </button>
        )}
      </div>
    );
  }

  return (
    <section className="mb-4 surface-card p-4 border-[var(--primary)]/20 bg-gradient-to-br from-[var(--primary-muted)] to-[var(--surface-container)]">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <Sparkles size={18} className="text-[var(--primary)] shrink-0" />
          <h2 className="font-semibold text-[var(--text-primary)]">{digest.headline}</h2>
        </div>
        {onRegenerate && (
          <button type="button" onClick={onRegenerate} className="text-xs text-link shrink-0">
            {copy.jobs.digestRegenerate}
          </button>
        )}
      </div>
      <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{digest.summary}</p>
      {digest.action_tips?.length > 0 && (
        <ul className="mt-2 text-xs text-[var(--text-secondary)] space-y-1 list-disc pl-4">
          {digest.action_tips.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      )}
      {digest.priority_jobs?.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-semibold text-[var(--text-disabled)] mb-2 uppercase tracking-wide">
            建议投递顺序
          </h3>
          <div className="space-y-2">
            {digest.priority_jobs.slice(0, 8).map((item, idx) => (
              <div
                key={item.job_id}
                className="flex flex-wrap items-center gap-2 bg-[var(--surface-container)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm"
              >
                <span className="text-[var(--text-disabled)] w-5 text-xs">{idx + 1}</span>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${
                    PRIORITY_STYLE[item.priority] || PRIORITY_STYLE.P2
                  }`}
                >
                  {PRIORITY_LABEL[item.priority] || item.priority}
                </span>
                {item.is_new && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-[var(--semantic-success-muted)] text-[var(--semantic-success)] rounded-[var(--radius-sm)]">新</span>
                )}
                <span className="font-medium text-[var(--text-primary)]">{item.company}</span>
                <span className="text-[var(--primary)]">{item.role}</span>
                {item.ai_summary && (
                  <span className="w-full text-xs text-[var(--text-secondary)]">{item.ai_summary}</span>
                )}
                <span className="text-xs text-[var(--text-secondary)]">{item.reasons?.join(" · ")}</span>
                {onApplyJob && (
                  <button
                    type="button"
                    onClick={() => onApplyJob(item.job_id)}
                    className="ml-auto text-xs text-link"
                  >
                    {copy.jobs.digestUseJd}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

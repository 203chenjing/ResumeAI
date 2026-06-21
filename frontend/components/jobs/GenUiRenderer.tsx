"use client";

import type { GenUiBlock } from "@/lib/types";
import { ExternalLink, Sparkles } from "lucide-react";
import { copy } from "@/lib/copy";

type Props = {
  blocks: GenUiBlock[];
  onApplyJob?: (jobId: string) => void;
  onAction?: (action: string, payload?: Record<string, unknown>) => void;
  onFilterChip?: (value: string) => void;
};

export default function GenUiRenderer({ blocks, onApplyJob, onAction, onFilterChip }: Props) {
  if (!blocks.length) return null;

  return (
    <div className="space-y-3 mt-2">
      {blocks.map((block, i) => {
        if (block.type === "match_summary") {
          return (
            <div key={i} className="rounded-lg border border-[var(--border-subtle)] bg-[var(--primary-muted)]/50 p-3 text-sm">
              <div className="flex items-center gap-1.5 font-medium text-[var(--text-primary)]">
                <Sparkles size={14} className="text-[var(--primary)]" /> {block.headline}
              </div>
              {block.summary && <p className="text-[var(--text-secondary)] mt-2">{block.summary}</p>}
              <ul className="mt-2 space-y-1">
                {block.top_scores.map((s, j) => (
                  <li key={j} className="flex justify-between text-xs text-[var(--text-primary)]">
                    <span>
                      {s.company} · {s.role}
                      {s.priority ? ` · ${s.priority}` : ""}
                    </span>
                    {s.score != null && (
                      <span className="font-semibold text-[var(--primary)]">{s.score}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          );
        }

        if (block.type === "filter_chips") {
          return (
            <div key={i} className="flex flex-wrap gap-2">
              {block.chips.map((c) => (
                <button
                  key={c.label}
                  type="button"
                  onClick={() => onFilterChip?.(c.value)}
                  className="px-2.5 py-1 rounded-full text-xs bg-[var(--surface-base)] hover:bg-[var(--primary-muted)] border border-[var(--border-subtle)]"
                >
                  {c.label}
                </button>
              ))}
            </div>
          );
        }

        if (block.type === "job_cards") {
          return (
            <div key={i} className="space-y-2 max-h-64 overflow-y-auto pr-1">
              {block.jobs.map((j) => (
                <div
                  key={j.id}
                  className="flex items-center justify-between gap-2 p-2.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-container)] text-sm"
                >
                  <div className="min-w-0">
                    <div className="font-medium truncate text-[var(--text-primary)]">{j.company}</div>
                    <div className="text-xs text-[var(--text-secondary)] truncate">{j.role}</div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {j.match_score != null && (
                      <span className="text-xs font-bold text-[var(--primary)]">{j.match_score}</span>
                    )}
                    {j.jd_url && (
                      <a
                        href={j.jd_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[var(--text-disabled)] hover:text-[var(--primary)]"
                      >
                        <ExternalLink size={14} />
                      </a>
                    )}
                    {j.id && onApplyJob && (
                      <button
                        type="button"
                        onClick={() => onApplyJob(j.id)}
                        className="text-xs px-2 py-1 rounded bg-[var(--primary)] text-white"
                      >
                        {copy.jobs.compareStartEdit}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          );
        }

        if (block.type === "actions") {
          return (
            <div key={i} className="flex flex-wrap gap-2">
              {block.buttons.map((b) => (
                <button
                  key={b.label}
                  type="button"
                  onClick={() => onAction?.(b.action, b.payload)}
                  className="px-3 py-1.5 rounded-lg text-xs btn-primary"
                >
                  {b.label}
                </button>
              ))}
            </div>
          );
        }

        return null;
      })}
    </div>
  );
}

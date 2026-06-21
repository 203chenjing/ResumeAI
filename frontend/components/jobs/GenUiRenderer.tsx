"use client";

import type { GenUiBlock } from "@/lib/types";
import { ExternalLink, Sparkles } from "lucide-react";

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
            <div key={i} className="rounded-lg border border-violet-100 bg-violet-50/80 p-3 text-sm">
              <div className="flex items-center gap-1.5 font-medium text-violet-900">
                <Sparkles size={14} /> {block.headline}
              </div>
              {block.algorithm && (
                <p className="text-xs text-violet-600 mt-1 font-mono">{block.algorithm}</p>
              )}
              {block.summary && <p className="text-slate-600 mt-2">{block.summary}</p>}
              <ul className="mt-2 space-y-1">
                {block.top_scores.map((s, j) => (
                  <li key={j} className="flex justify-between text-xs text-slate-700">
                    <span>
                      {s.company} · {s.role}
                      {s.priority ? ` · ${s.priority}` : ""}
                    </span>
                    {s.score != null && <span className="font-semibold text-violet-700">{s.score}</span>}
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
                  className="px-2.5 py-1 rounded-full text-xs bg-slate-100 hover:bg-blue-100 border"
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
                  className="flex items-center justify-between gap-2 p-2.5 rounded-lg border bg-white text-sm"
                >
                  <div className="min-w-0">
                    <div className="font-medium truncate">{j.company}</div>
                    <div className="text-xs text-slate-500 truncate">{j.role}</div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {j.match_score != null && (
                      <span className="text-xs font-bold text-blue-700">{j.match_score}</span>
                    )}
                    {j.jd_url && (
                      <a
                        href={j.jd_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-slate-400 hover:text-blue-600"
                      >
                        <ExternalLink size={14} />
                      </a>
                    )}
                    {j.id && onApplyJob && (
                      <button
                        type="button"
                        onClick={() => onApplyJob(j.id)}
                        className="text-xs px-2 py-1 rounded bg-blue-600 text-white"
                      >
                        改简历
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
                  className="px-3 py-1.5 rounded-lg text-xs bg-slate-800 text-white hover:bg-slate-700"
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

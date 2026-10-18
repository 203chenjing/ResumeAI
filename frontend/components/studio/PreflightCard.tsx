"use client";

import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, Scissors, Undo2 } from "lucide-react";
import clsx from "clsx";
import { copy } from "@/lib/copy";
import type { PreflightResult } from "@/lib/types";

interface Props {
  preflight: PreflightResult | null;
  loading: boolean;
  compressing: boolean;
  isFinalized: boolean;
  compressNote?: string;
  canUndoCompress?: boolean;
  onRefresh: () => void;
  onCompress: () => void;
  onForce: () => void;
  onGoEdit: () => void;
  onUndoCompress: () => void;
}

/**
 * 预检卡片：把「定稿被拒」提前成一份带出路的体检单。
 *
 * 每条问题都必须带一个动作（压缩 / 去改稿 / 仍然导出），不允许出现死路。
 */
export default function PreflightCard({
  preflight,
  loading,
  compressing,
  isFinalized,
  compressNote,
  canUndoCompress,
  onRefresh,
  onCompress,
  onForce,
  onGoEdit,
  onUndoCompress,
}: Props) {
  if (!preflight && !loading) return null;

  const issues = preflight?.issues || [];
  const blocking = issues.filter((i) => i.blocking);
  const warnings = issues.filter((i) => !i.blocking);
  const passed = preflight?.passed ?? false;
  const pageCount = preflight?.page_count ?? preflight?.metrics.estimated_pages ?? 1;
  const hasPageIssue = issues.some((i) => i.code === "page_count");
  const needsCompress = issues.some((i) => i.action === "compress");

  return (
    <div
      className={clsx(
        "section-card text-sm space-y-3",
        passed
          ? "border-[var(--semantic-success)]/25"
          : "border-[var(--semantic-warning)]/40"
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium inline-flex items-center gap-1.5">
          {passed ? (
            <CheckCircle2 size={15} className="text-[var(--semantic-success)]" />
          ) : (
            <AlertTriangle size={15} className="text-[var(--semantic-warning)]" />
          )}
          {copy.preflight.title}
        </span>
        <span className="text-xs text-[var(--text-secondary)]">
          {loading
            ? copy.preflight.checking
            : passed
              ? copy.preflight.passed
              : copy.preflight.blocked(blocking.length)}
        </span>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading || compressing}
          className="ml-auto text-xs text-[var(--text-secondary)] hover:text-[var(--primary)] inline-flex items-center gap-1"
        >
          <RefreshCw size={12} className={clsx(loading && "animate-spin")} />
          {copy.preflight.rerun}
        </button>
      </div>

      {preflight && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--text-secondary)] tabular-nums">
          <span>
            {copy.capacity.pages(pageCount)} · {copy.export.charsApprox(preflight.metrics.char_count)}
          </span>
          <span
            className={clsx(
              preflight.metrics.experience_items > preflight.metrics.experience_limit &&
                "text-[var(--semantic-warning)]"
            )}
          >
            {copy.capacity.items(
              preflight.metrics.experience_items,
              preflight.metrics.experience_limit
            )}
          </span>
          <span
            className={clsx(
              preflight.metrics.skill_items !== preflight.metrics.skill_limit &&
                "text-[var(--semantic-warning)]"
            )}
          >
            {copy.capacity.skills(
              preflight.metrics.skill_items,
              preflight.metrics.skill_limit
            )}
          </span>
        </div>
      )}

      {blocking.length > 0 && (
        <ul className="space-y-2">
          {blocking.map((issue) => (
            <li key={`${issue.code}-${issue.message}`} className="rounded-[var(--radius-sm)] bg-[var(--surface-base)] p-2.5">
              <p className="text-[var(--text-primary)]">{issue.message}</p>
              <p className="text-xs text-[var(--text-secondary)] mt-1">{issue.hint}</p>
            </li>
          ))}
        </ul>
      )}

      {warnings.length > 0 && (
        <ul className="space-y-1 text-xs text-[var(--text-secondary)]">
          {warnings.map((issue) => (
            <li key={`${issue.code}-${issue.message}`}>· {issue.message}</li>
          ))}
        </ul>
      )}

      {compressNote && <p className="text-xs text-[var(--text-secondary)]">{compressNote}</p>}

      {!isFinalized && (
        <div className="flex flex-wrap items-center gap-2 pt-1">
          {needsCompress && (
            <button
              type="button"
              onClick={onCompress}
              disabled={compressing || loading}
              className="btn-secondary text-xs py-1.5"
            >
              {compressing ? <Loader2 size={13} className="animate-spin" /> : <Scissors size={13} />}
              {compressing ? copy.preflight.compressing : copy.preflight.compress}
            </button>
          )}
          {canUndoCompress && (
            <button
              type="button"
              onClick={onUndoCompress}
              disabled={compressing}
              className="btn-secondary text-xs py-1.5"
            >
              <Undo2 size={13} /> {copy.preflight.undoCompress}
            </button>
          )}
          <button type="button" onClick={onGoEdit} className="btn-secondary text-xs py-1.5">
            {copy.preflight.goEdit}
          </button>
          {hasPageIssue && pageCount > 1 && (
            <button
              type="button"
              onClick={onForce}
              disabled={compressing || loading}
              className="text-xs px-3 py-1.5 rounded-[var(--radius-full)] border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:border-[var(--semantic-warning)] hover:text-[var(--semantic-warning)]"
            >
              {copy.preflight.force(pageCount)}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

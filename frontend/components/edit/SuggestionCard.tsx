"use client";

import { useState } from "react";
import { Check, X, RefreshCw, Undo2, Loader2 } from "lucide-react";
import clsx from "clsx";
import { Suggestion } from "@/lib/types";
import { copy } from "@/lib/copy";

const TYPE_LABELS: Record<string, { label: string; color: string }> = {
  wording: { label: copy.suggestion.types.wording, color: "bg-[var(--primary-muted)] text-[var(--primary)]" },
  star: { label: copy.suggestion.types.star, color: "chip-star" },
  keyword: { label: copy.suggestion.types.keyword, color: "chip-keyword" },
  structure: { label: copy.suggestion.types.structure, color: "chip-structure" },
  delete: { label: copy.suggestion.types.delete, color: "chip-delete" },
};

const SECTION_LABELS: Record<string, string> = copy.suggestion.sections;

interface Props {
  suggestion: Suggestion;
  onAccept: () => void | Promise<void>;
  onReject: () => void | Promise<void>;
  onUndo: () => void | Promise<void>;
  onAdjust: (instruction: string) => void | Promise<void>;
  onFocus?: () => void;
  busy?: boolean;
  highlight?: boolean;
}

export default function SuggestionCard({ suggestion, onAccept, onReject, onUndo, onAdjust, onFocus, busy, highlight }: Props) {
  const [showAdjust, setShowAdjust] = useState(false);
  const [instruction, setInstruction] = useState("");
  const t = TYPE_LABELS[suggestion.type] || {
    label: suggestion.type,
    color: "bg-[var(--surface-base)] text-[var(--text-secondary)]",
  };
  const sectionLabel = SECTION_LABELS[suggestion.section] || suggestion.section;

  // 采纳建议 = 花版面预算：标出这条会多占/省下多少字，避免无脑点采纳
  const charDelta =
    (suggestion.suggested_text?.length || 0) - (suggestion.original_text?.length || 0);

  const statusBorder = {
    pending: "border-[var(--border-subtle)]",
    accepted: "border-[var(--semantic-success-border)] bg-[var(--semantic-success-muted)]/30",
    rejected: "border-[var(--border-subtle)] bg-[var(--surface-base)] opacity-60",
    adjusted: "border-[var(--primary)]/40 bg-[var(--primary-muted)]/50",
  }[suggestion.status];

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onFocus}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onFocus?.();
      }}
      className={clsx(
        "surface-card p-4 text-sm transition-shadow cursor-pointer",
        statusBorder,
        highlight && "ring-2 ring-[var(--primary)] ring-offset-2"
      )}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className={clsx("px-2 py-0.5 rounded-[var(--radius-sm)] text-xs font-medium", t.color)}>{t.label}</span>
        <span className="px-2 py-0.5 rounded-[var(--radius-sm)] bg-[var(--surface-base)] text-[var(--text-secondary)] text-xs">
          {sectionLabel}
        </span>
        {charDelta !== 0 && (
          <span
            className={clsx(
              "px-1.5 py-0.5 rounded-[var(--radius-sm)] text-xs tabular-nums",
              charDelta > 0
                ? "text-[var(--semantic-warning)] border border-[var(--semantic-warning)]/30"
                : "text-[var(--semantic-success)] border border-[var(--semantic-success)]/30"
            )}
            title={charDelta > 0 ? "采纳后正文变长，会占用一页预算" : "采纳后正文变短，省出版面"}
          >
            {charDelta > 0 ? `+${charDelta}` : charDelta} 字
          </span>
        )}
        {suggestion.status === "accepted" && (
          <span className="text-[var(--semantic-success)] text-xs ml-auto">✓ {copy.edit.statusAccepted}</span>
        )}
        {suggestion.status === "rejected" && (
          <span className="text-[var(--text-disabled)] text-xs ml-auto">{copy.edit.statusRejected}</span>
        )}
        {suggestion.status === "adjusted" && (
          <span className="text-[var(--primary)] text-xs ml-auto">{copy.edit.statusAdjusted}</span>
        )}
      </div>

      {suggestion.original_text && suggestion.type !== "delete" && (
        <div className="mb-2">
          <div className="text-xs text-[var(--text-disabled)] mb-1">{copy.suggestion.original}</div>
          <div className="p-2 bg-[var(--surface-base)] rounded-[var(--radius-sm)] text-[var(--text-secondary)] text-sm line-through">
            {suggestion.original_text}
          </div>
        </div>
      )}

      <div className="mb-2">
        <div className="text-xs text-[var(--text-disabled)] mb-1">
          {suggestion.type === "delete" ? copy.suggestion.delete : copy.suggestion.after}
        </div>
        <div className="p-2 bg-[var(--semantic-success-muted)] rounded-[var(--radius-sm)] text-[var(--text-primary)] text-sm">
          {suggestion.type === "delete" ? suggestion.original_text : suggestion.suggested_text}
        </div>
      </div>

      <div className="text-xs text-[var(--text-secondary)] mb-2">
        <span className="font-medium text-[var(--text-primary)]">{copy.suggestion.reason}：</span>
        {suggestion.reason}
      </div>

      {suggestion.jd_match_points.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {suggestion.jd_match_points.map((p, i) => (
            <span
              key={i}
              className="px-1.5 py-0.5 bg-[var(--primary-muted)] text-[var(--primary)] rounded-[var(--radius-sm)] text-xs"
            >
              {p}
            </span>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        {suggestion.status === "pending" || suggestion.status === "adjusted" ? (
          <>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onAccept();
              }}
              disabled={busy}
              className="flex-1 px-2 py-1.5 bg-[var(--semantic-success)] text-white rounded-[var(--radius-full)] text-xs hover:opacity-90 flex items-center justify-center gap-1 disabled:opacity-50"
            >
              {busy ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
              {copy.suggestion.accept}
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onReject();
              }}
              disabled={busy}
              className="flex-1 px-2 py-1.5 btn-secondary text-xs py-1.5 justify-center disabled:opacity-50"
            >
              <X size={12} /> {copy.suggestion.reject}
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setShowAdjust(!showAdjust);
              }}
              disabled={busy}
              className="px-2 py-1.5 bg-[var(--primary-muted)] text-[var(--primary)] rounded-[var(--radius-full)] text-xs hover:opacity-90 flex items-center gap-1 disabled:opacity-50"
            >
              <RefreshCw size={12} /> {copy.suggestion.adjust}
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onUndo();
            }}
            disabled={busy}
            className="flex-1 px-2 py-1.5 bg-[var(--surface-base)] text-[var(--text-secondary)] rounded-[var(--radius-sm)] text-xs hover:bg-[var(--border-subtle)] flex items-center justify-center gap-1 disabled:opacity-50"
          >
            <Undo2 size={12} /> {copy.suggestion.undo}
          </button>
        )}
      </div>

      {showAdjust && (
        <div className="mt-2 p-2 bg-[var(--primary-muted)]/50 rounded-[var(--radius-sm)]">
          <input
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder={copy.suggestion.adjustPlaceholder}
            className="w-full px-2 py-1 text-xs input-field"
          />
          <button
            onClick={async () => {
              if (!instruction.trim()) return;
              await onAdjust(instruction);
              setInstruction("");
              setShowAdjust(false);
            }}
            className="mt-2 px-3 py-1 bg-[var(--primary)] text-white rounded-[var(--radius-full)] text-xs hover:opacity-90"
          >
            {copy.suggestion.adjustSubmit}
          </button>
        </div>
      )}
    </div>
  );
}

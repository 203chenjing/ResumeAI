"use client";

import { useState } from "react";
import { Check, X, RefreshCw, Undo2, Loader2 } from "lucide-react";
import clsx from "clsx";
import { Suggestion } from "@/lib/types";

const TYPE_LABELS: Record<string, { label: string; color: string }> = {
  wording: { label: "措辞优化", color: "bg-blue-100 text-blue-700" },
  star: { label: "STAR 改写", color: "bg-purple-100 text-purple-700" },
  keyword: { label: "关键词嵌入", color: "bg-green-100 text-green-700" },
  structure: { label: "结构调整", color: "bg-amber-100 text-amber-700" },
  delete: { label: "建议删除", color: "bg-red-100 text-red-700" },
};

interface Props {
  suggestion: Suggestion;
  onAccept: () => void | Promise<void>;
  onReject: () => void | Promise<void>;
  onUndo: () => void | Promise<void>;
  onAdjust: (instruction: string) => void | Promise<void>;
  busy?: boolean;
  highlight?: boolean;
}

export default function SuggestionCard({ suggestion, onAccept, onReject, onUndo, onAdjust, busy, highlight }: Props) {
  const [showAdjust, setShowAdjust] = useState(false);
  const [instruction, setInstruction] = useState("");
  const t = TYPE_LABELS[suggestion.type] || { label: suggestion.type, color: "bg-slate-100 text-slate-700" };

  const statusBorder = {
    pending: "border-slate-200",
    accepted: "border-green-400 bg-green-50/30",
    rejected: "border-slate-300 bg-slate-50 opacity-60",
    adjusted: "border-blue-400 bg-blue-50/30",
  }[suggestion.status];

  return (
    <div
      className={clsx(
        "border rounded-lg p-3 text-sm transition-shadow",
        statusBorder,
        highlight && "ring-2 ring-violet-500 ring-offset-2 shadow-md animate-pulse"
      )}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className={clsx("px-2 py-0.5 rounded text-xs font-medium", t.color)}>{t.label}</span>
        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-xs">{suggestion.section}</span>
        {suggestion.status === "accepted" && <span className="text-green-600 text-xs ml-auto">✓ 已接受</span>}
        {suggestion.status === "rejected" && <span className="text-slate-500 text-xs ml-auto">已拒绝</span>}
        {suggestion.status === "adjusted" && <span className="text-blue-600 text-xs ml-auto">已调整</span>}
      </div>

      {suggestion.original_text && suggestion.type !== "delete" && (
        <div className="mb-2">
          <div className="text-xs text-slate-500 mb-1">原文</div>
          <div className="p-2 bg-slate-50 rounded text-slate-700 text-[13px] line-through decoration-slate-400">
            {suggestion.original_text}
          </div>
        </div>
      )}

      <div className="mb-2">
        <div className="text-xs text-slate-500 mb-1">{suggestion.type === "delete" ? "删除：" : "修改后"}</div>
        <div className="p-2 bg-green-50 rounded text-slate-900 text-[13px]">
          {suggestion.type === "delete" ? suggestion.original_text : suggestion.suggested_text}
        </div>
      </div>

      <div className="text-xs text-slate-600 mb-2">
        <span className="font-medium text-slate-700">原因：</span>
        {suggestion.reason}
      </div>

      {suggestion.jd_match_points.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {suggestion.jd_match_points.map((p, i) => (
            <span key={i} className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-[11px]">
              {p}
            </span>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        {suggestion.status === "pending" || suggestion.status === "adjusted" ? (
          <>
            <button
              onClick={onAccept}
              disabled={busy}
              className="flex-1 px-2 py-1.5 bg-green-600 text-white rounded text-xs hover:bg-green-700 flex items-center justify-center gap-1"
            >
              {busy ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
              接受
            </button>
            <button
              onClick={onReject}
              disabled={busy}
              className="flex-1 px-2 py-1.5 bg-slate-200 text-slate-700 rounded text-xs hover:bg-slate-300 flex items-center justify-center gap-1"
            >
              <X size={12} /> 拒绝
            </button>
            <button
              onClick={() => setShowAdjust(!showAdjust)}
              disabled={busy}
              className="px-2 py-1.5 bg-blue-100 text-blue-700 rounded text-xs hover:bg-blue-200 flex items-center gap-1"
            >
              <RefreshCw size={12} /> 调整
            </button>
          </>
        ) : (
          <button
            onClick={onUndo}
            disabled={busy}
            className="flex-1 px-2 py-1.5 bg-slate-100 text-slate-700 rounded text-xs hover:bg-slate-200 flex items-center justify-center gap-1"
          >
            <Undo2 size={12} /> 撤销
          </button>
        )}
      </div>

      {showAdjust && (
        <div className="mt-2 p-2 bg-blue-50 rounded">
          <input
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="例如：不要太夸张，保持真实"
            className="w-full px-2 py-1 text-xs border border-blue-200 rounded"
          />
          <button
            onClick={async () => {
              if (!instruction.trim()) return;
              await onAdjust(instruction);
              setInstruction("");
              setShowAdjust(false);
            }}
            className="mt-2 px-3 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700"
          >
            提交调整
          </button>
        </div>
      )}
    </div>
  );
}

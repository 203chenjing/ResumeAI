"use client";

import { useEffect, useRef, useState } from "react";
import { useAppStore, type DensityInfo, type FinalizeStatus } from "@/stores/useAppStore";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import SuggestionCard from "./SuggestionCard";
import { Filter, CheckCheck } from "lucide-react";
import clsx from "clsx";
import { applyEditChatDone, buildEditUiContext } from "@/lib/editSessionSync";

import ConfirmDialog from "@/components/ui/ConfirmDialog";

export default function SuggestionPanel() {
  const {
    sessionId,
    suggestions,
    upsertSuggestion,
    setSuggestions,
    setCurrentMarkdown,
    setFinalizedMarkdown,
    setFinalizeStatus,
    setMatchResult,
    setDensity,
    mergeSuggestions,
    setFilter,
    setHighlightSuggestionIds,
    highlightSuggestionIds,
    filter,
    pushToast,
  } = useAppStore();
  const [busyId, setBusyId] = useState("");
  const [batchConfirm, setBatchConfirm] = useState(false);
  const [batchBusy, setBatchBusy] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  const sessionSetters = {
    setSuggestions,
    mergeSuggestions,
    setCurrentMarkdown,
    setFinalizedMarkdown,
    setFinalizeStatus,
    setMatchResult,
    setDensity,
    setFilter,
    setHighlightSuggestionIds,
  };

  useEffect(() => {
    if (highlightSuggestionIds.length === 0 || !listRef.current) return;
    const first = listRef.current.querySelector(`[data-sug-id="${highlightSuggestionIds[0]}"]`);
    first?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    const t = window.setTimeout(() => setHighlightSuggestionIds([]), 4000);
    return () => window.clearTimeout(t);
  }, [highlightSuggestionIds, setHighlightSuggestionIds]);

  const filtered = suggestions.filter((s) => {
    if (filter === "all") return true;
    if (filter === "pending") return s.status === "pending" || s.status === "adjusted";
    return s.status === filter;
  });

  async function setStatus(id: string, status: "accepted" | "rejected" | "pending") {
    setBusyId(id);
    try {
      const res = await api.updateSuggestionStatus(sessionId, id, status, getClientId());
      if (res.success && res.data) {
        upsertSuggestion(res.data.suggestion);
        setCurrentMarkdown(res.data.current_markdown);
        if (res.data.suggestions) setSuggestions(res.data.suggestions);
        if (res.data.match) setMatchResult(res.data.match);
        if (res.data.density) {
          setDensity(res.data.density as DensityInfo);
          if (status === "accepted" && res.data.density.status === "sparse") {
            pushToast(res.data.density.message, "warning", 8000);
          }
        }
        if (res.data.finalize_status) setFinalizeStatus(res.data.finalize_status as FinalizeStatus);

        const labels = { accepted: "已接受", rejected: "已拒绝", pending: "已撤销" };
        pushToast(`建议 ${labels[status]}`, status === "accepted" ? "success" : "info");
      }
    } catch (e) {
      pushToast((e as Error).message, "error");
    } finally {
      setBusyId("");
    }
  }

  async function adjust(id: string, instruction: string) {
    setBusyId(id);
    try {
      const res = await api.adjustSuggestion(sessionId, id, instruction);
      if (res.success && res.data) {
        upsertSuggestion(res.data.updated);
        pushToast("建议已按指令调整", "success");
      }
    } catch (e) {
      pushToast((e as Error).message, "error");
    } finally {
      setBusyId("");
    }
  }

  async function acceptAllSafe() {
    setBatchBusy(true);
    try {
      await api.streamEditChatAgent(
        {
          session_id: sessionId,
          message: "",
          client_id: getClientId(),
          ui_context: buildEditUiContext({ filter, suggestions }),
          confirmed_action: {
            action: "review_suggestions",
            action_input: { policy: "accept_safe" },
          },
        },
        (event) => {
          if (event.type === "done") {
            applyEditChatDone(event, sessionSetters);
            pushToast(event.reply || "已批量处理建议", "success");
          }
        },
        (err) => pushToast(err.message, "error")
      );
    } finally {
      setBatchBusy(false);
      setBatchConfirm(false);
    }
  }

  const counts = {
    all: suggestions.length,
    pending: suggestions.filter((s) => s.status === "pending" || s.status === "adjusted").length,
    accepted: suggestions.filter((s) => s.status === "accepted").length,
    rejected: suggestions.filter((s) => s.status === "rejected").length,
  };

  return (
    <div className="h-full flex flex-col bg-slate-50">
      <ConfirmDialog
        open={batchConfirm}
        title="批量接受安全建议"
        message={`将自动接受 ${counts.pending} 条待处理建议中的「安全」项（跳过 delete/过稀时的 structure），是否继续？`}
        confirmLabel="确认接受"
        onConfirm={acceptAllSafe}
        onCancel={() => setBatchConfirm(false)}
      />
      <div className="px-4 py-3 border-b border-slate-200 bg-white flex items-center gap-2 flex-wrap">
        <Filter size={14} className="text-slate-500" />
        <span className="text-sm font-medium">修改建议 ({counts.all})</span>
        {counts.pending > 0 && (
          <button
            type="button"
            disabled={batchBusy}
            onClick={() => setBatchConfirm(true)}
            className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            <CheckCheck size={12} /> 安全批量接受
          </button>
        )}
        <div className="ml-auto flex gap-1">
          {(["all", "pending", "accepted", "rejected"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={clsx(
                "px-2 py-1 rounded text-xs",
                filter === f ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              )}
            >
              {f === "all" ? "全部" : f === "pending" ? "待处理" : f === "accepted" ? "已接受" : "已拒绝"}
              <span className="ml-1 opacity-70">{counts[f]}</span>
            </button>
          ))}
        </div>
      </div>

      <div ref={listRef} className="flex-1 overflow-auto p-3 space-y-3">
        {filtered.length === 0 && (
          <div className="text-center text-sm text-slate-500 py-8">
            {filter === "pending" ? "暂无待处理建议" : "暂无建议"}
          </div>
        )}
        {filtered.map((s) => (
          <div key={s.id} data-sug-id={s.id}>
            <SuggestionCard
              suggestion={s}
              busy={busyId === s.id}
              highlight={highlightSuggestionIds.includes(s.id)}
              onAccept={() => setStatus(s.id, "accepted")}
              onReject={() => setStatus(s.id, "rejected")}
              onUndo={() => setStatus(s.id, "pending")}
              onAdjust={(ins) => adjust(s.id, ins)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

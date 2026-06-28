"use client";

import { useEffect, useRef, useState } from "react";
import { useAppStore, type DensityInfo, type FinalizeStatus } from "@/stores/useAppStore";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import SuggestionCard from "./SuggestionCard";
import { CheckCheck } from "lucide-react";
import clsx from "clsx";
import { applyEditChatDone, buildEditUiContext } from "@/lib/editSessionSync";
import { copy } from "@/lib/copy";
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
        pushToast(copy.edit.adjusted, "success");
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
            pushToast(event.reply || copy.edit.batchDone, "success");
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
    <div className="h-full flex flex-col bg-[var(--surface-base)]">
      <ConfirmDialog
        open={batchConfirm}
        title={copy.edit.batchSafeTitle}
        message={copy.edit.batchSafeMsg(counts.pending)}
        confirmLabel={copy.edit.batchConfirm}
        onConfirm={acceptAllSafe}
        onCancel={() => setBatchConfirm(false)}
      />
      <div className="toolbar">
        <span className="text-sm font-medium text-[var(--text-primary)]">{copy.edit.suggestions(counts.all)}</span>
        {counts.pending > 0 && (
          <button
            type="button"
            disabled={batchBusy}
            onClick={() => setBatchConfirm(true)}
            className="btn-primary text-xs py-1.5"
            style={{ background: "var(--semantic-success)" }}
          >
            <CheckCheck size={12} /> {copy.edit.batchSafe}
          </button>
        )}
        <div className="ml-auto flex gap-0.5 p-0.5 rounded-[var(--radius-full)] bg-[var(--surface-base)]">
          {(["all", "pending", "accepted", "rejected"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={clsx(
                "filter-chip",
                filter === f ? "filter-chip-active" : "filter-chip-inactive"
              )}
            >
              {f === "all" ? copy.edit.filterAll : f === "pending" ? copy.edit.filterPending : f === "accepted" ? copy.edit.filterAccepted : copy.edit.filterRejected}
              <span className="ml-1 opacity-70">{counts[f]}</span>
            </button>
          ))}
        </div>
      </div>

      <div ref={listRef} className="flex-1 overflow-auto p-4 space-y-3">
        {filtered.length === 0 && (
          <div className="empty-state">
            {filter === "pending" ? copy.edit.noPending : copy.edit.noSuggestions}
          </div>
        )}
        {filtered.map((s) => (
          <div key={s.id} data-sug-id={s.id}>
            <SuggestionCard
              suggestion={s}
              busy={busyId === s.id}
              highlight={highlightSuggestionIds.includes(s.id)}
              onFocus={() => setHighlightSuggestionIds([s.id])}
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

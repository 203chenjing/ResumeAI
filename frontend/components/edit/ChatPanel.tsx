"use client";

import { useEffect, useState } from "react";
import { Send, Loader2, Sparkles } from "lucide-react";
import { useAppStore } from "@/stores/useAppStore";
import { api } from "@/lib/api";
import { buildQuickPrompts, getClientId, loadLocalMemory, saveLocalMemory, UserMemory } from "@/lib/userMemory";
import { applyEditChatDone, buildEditUiContext } from "@/lib/editSessionSync";
import { copy } from "@/lib/copy";
import ConfirmDialog from "@/components/ui/ConfirmDialog";

type PendingConfirm = {
  action: string;
  input?: Record<string, unknown>;
  message: string;
};

export default function ChatPanel() {
  const {
    sessionId,
    chatMessages,
    appendChat,
    updateLastAssistant,
    setLastAssistant,
    setSuggestions,
    mergeSuggestions,
    setCurrentMarkdown,
    setFinalizedMarkdown,
    setMatchResult,
    setFinalizeStatus,
    setDensity,
    setFilter,
    setHighlightSuggestionIds,
    setCopilotOpen,
    suggestions,
    filter,
    pushToast,
  } = useAppStore();
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm | null>(null);
  const [quickPrompts, setQuickPrompts] = useState<string[]>(() => buildQuickPrompts());

  useEffect(() => {
    const local = loadLocalMemory();
    setQuickPrompts(buildQuickPrompts(local));
    api.getUserMemory(getClientId()).then((res) => {
      const remote = (res.data || {}) as { preferences?: UserMemory["preferences"] };
      if (remote.preferences) {
        const merged = {
          ...local,
          preferences: { ...local.preferences, ...remote.preferences },
        };
        setQuickPrompts(buildQuickPrompts(merged));
      }
    }).catch(() => {});
  }, []);

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
    setCopilotOpen,
  };

  async function downloadExport() {
    try {
      const blob = await api.exportPdf(sessionId, "standard");
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "resume.pdf";
      a.click();
      URL.revokeObjectURL(url);
      pushToast(copy.edit.pdfDownloading, "success");
    } catch (e) {
      pushToast((e as Error).message, "error");
    }
  }

  async function runAgent(
    text: string,
    confirmed?: PendingConfirm
  ) {
    if (!sessionId) return;
    if (!confirmed) {
      appendChat({ role: "user", content: text });
      appendChat({ role: "assistant", content: "" });
    }
    setInput("");
    setStreaming(true);

    await api.streamEditChatAgent(
      {
        session_id: sessionId,
        message: text,
        client_id: getClientId(),
        ui_context: buildEditUiContext({ filter, suggestions }),
        confirmed_action: confirmed
          ? { action: confirmed.action, action_input: confirmed.input }
          : undefined,
      },
      (event) => {
        if (event.type === "text") updateLastAssistant(event.content);
        if (event.type === "thought") {
          updateLastAssistant(`\n💭 ${event.content}\n`);
        }
        if (event.type === "tool_call") {
          updateLastAssistant(`\n🔧 ${event.action}…\n`);
        }
        if (event.type === "confirmation_required") {
          setPendingConfirm({
            action: event.action,
            input: event.input,
            message: event.message,
          });
          setLastAssistant(event.message);
          setStreaming(false);
        }
        if (event.type === "export_ready") {
          downloadExport();
        }
        if (event.type === "customization_update" && event.updates) {
          const local = loadLocalMemory();
          const prefs = { ...local.preferences, ...event.updates };
          saveLocalMemory({ preferences: prefs });
          setQuickPrompts(buildQuickPrompts({ ...local, preferences: prefs }));
        }
        if (event.type === "done") {
          if (event.reply) setLastAssistant(event.reply);
          const { newCount, highlightIds, pendingDelta } = applyEditChatDone(event, sessionSetters);
          const pendingN = event.session?.suggestions?.filter(
            (s) => s.status === "pending" || s.status === "adjusted"
          ).length;
          if (newCount > 0) {
            pushToast(copy.edit.syncSuggestions(newCount), "success");
          } else if (highlightIds.length > 0 || (pendingN && /待处理|修改建议|已生成/.test(event.reply || ""))) {
            pushToast(copy.edit.highlightSuggestions(pendingN || highlightIds.length), "info");
          } else if (
            /已生成\s*\d+\s*条/.test(event.reply || "") &&
            newCount === 0 &&
            pendingDelta === 0
          ) {
            pushToast(copy.edit.syncFailed, "warning");
          }
          setStreaming(false);
        }
      },
      (err) => {
        updateLastAssistant(`\n\n[错误] ${err.message}`);
        pushToast(err.message, "error");
        setStreaming(false);
      }
    );
  }

  async function send(text: string) {
    if (!text.trim() || streaming || !sessionId) return;
    await runAgent(text);
  }

  async function onConfirmPending() {
    if (!pendingConfirm) return;
    const p = pendingConfirm;
    setPendingConfirm(null);
    setStreaming(true);
    appendChat({ role: "assistant", content: "正在执行确认操作…" });
    await runAgent("", p);
  }

  return (
    <>
      <ConfirmDialog
        open={!!pendingConfirm}
        title="确认一下"
        message={pendingConfirm?.message || ""}
        confirmLabel={copy.common.confirm}
        variant={pendingConfirm?.action === "finalize_resume" ? "danger" : "warning"}
        onConfirm={onConfirmPending}
        onCancel={() => setPendingConfirm(null)}
      />

      <div className="h-full flex flex-col bg-[var(--surface-container)] border-l border-[var(--border-subtle)]">
        <div className="px-4 py-3 border-b border-[var(--border-subtle)] flex items-center gap-2">
          <Sparkles size={14} className="text-[var(--primary)]" />
          <span className="text-sm font-medium text-[var(--text-primary)]">{copy.edit.assistant}</span>
          <span className="text-xs text-[var(--text-disabled)]">{copy.edit.assistantHint}</span>
        </div>

        <div className="flex-1 overflow-auto p-3 space-y-3 text-sm">
          {chatMessages.length === 0 && (
            <div className="text-center text-[var(--text-disabled)] text-xs py-8">
              {copy.edit.assistantEmpty}
              <div className="mt-3 grid grid-cols-2 gap-2">
                {quickPrompts.map((p) => (
                  <button
                    key={p}
                    onClick={() => send(p)}
                    className="p-2 text-left text-xs bg-[var(--surface-base)] rounded hover:bg-[var(--primary-muted)] text-[var(--text-secondary)]"
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          )}
          {chatMessages.map((m, i) => (
            <div
              key={i}
              className={
                m.role === "user"
                  ? "ml-6 p-2 bg-[var(--primary-muted)] rounded-lg text-[var(--text-primary)]"
                  : "mr-6 p-2 bg-[var(--surface-base)] rounded-lg text-[var(--text-primary)] whitespace-pre-wrap"
              }
            >
              {m.content || (streaming && i === chatMessages.length - 1 ? "..." : "")}
            </div>
          ))}
        </div>

        <div className="p-3 border-t border-[var(--border-subtle)]">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              placeholder={copy.edit.assistantPlaceholder}
              disabled={streaming}
              className="flex-1 px-3 py-2 border border-[var(--border-subtle)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
            />
            <button
              onClick={() => send(input)}
              disabled={streaming || !input.trim()}
              className="px-3 py-2 bg-[var(--primary)] text-white rounded-lg hover:opacity-90 disabled:opacity-40"
            >
              {streaming ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

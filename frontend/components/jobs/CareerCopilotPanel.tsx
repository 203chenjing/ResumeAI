"use client";

import { useState } from "react";
import { Sparkles, Loader2, X } from "lucide-react";
import ChatInput from "@/components/ui/ChatInput";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import type { CareerCopilotEvent, GenUiBlock } from "@/lib/types";
import GenUiRenderer from "@/components/jobs/GenUiRenderer";
import { copy } from "@/lib/copy";

type Message = { role: "user" | "assistant"; text: string; blocks?: GenUiBlock[] };

const STARTERS = [
  "推荐最适合我的岗位",
  "今天优先投哪些？",
  "北京有哪些相关岗位？",
  copy.jobs.refresh,
];

type Props = {
  onApplyJob: (jobId: string) => void;
  onCrawl: () => void;
  onFilter: (q: string) => void;
  onCompare: (ids: string[]) => void;
};

export default function CareerCopilotPanel({
  onApplyJob,
  onCrawl,
  onFilter,
  onCompare,
}: Props) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      text: copy.jobs.copilotIntro,
    },
  ]);

  async function send(text: string) {
    const q = text.trim();
    if (!q || streaming) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setStreaming(true);
    let reply = "";
    let blocks: GenUiBlock[] = [];

    await api.streamCareerCopilot(
      getClientId(),
      q,
      (ev: CareerCopilotEvent) => {
        if (ev.type === "text") reply = ev.content;
        if (ev.type === "gen_ui") blocks = [...blocks, ev.block];
        if (ev.type === "done") {
          reply = ev.reply || reply;
          if (ev.blocks?.length) blocks = ev.blocks;
        }
      },
      (err) => {
        reply = err.message;
      }
    );

    setMessages((m) => [...m, { role: "assistant", text: reply || "已更新。", blocks }]);
    setStreaming(false);
  }

  function handleAction(action: string, payload?: Record<string, unknown>) {
    if (action === "crawl") onCrawl();
    if (action === "compare" && payload?.job_ids) onCompare(payload.job_ids as string[]);
    if (action === "navigate" && payload?.path) window.location.href = String(payload.path);
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2 px-4 py-3 rounded-full shadow-lg bg-[var(--primary)] text-white text-sm hover:opacity-90"
      >
        <Sparkles size={18} /> {copy.jobs.copilotTitle}
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-40 w-[min(420px,calc(100vw-2rem))] flex flex-col rounded-2xl border border-[var(--border-subtle)] shadow-2xl bg-[var(--surface-container)] overflow-hidden max-h-[min(640px,calc(100vh-4rem))]">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-subtle)]">
        <div className="flex items-center gap-2 text-sm font-medium text-[var(--text-primary)]">
          <Sparkles size={16} className="text-[var(--primary)]" />
          {copy.jobs.copilotTitle}
        </div>
        <button type="button" onClick={() => setOpen(false)} className="btn-ghost p-1" aria-label={copy.common.close}>
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3 text-sm">
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : ""}>
            <div
              className={`inline-block max-w-[95%] rounded-[var(--radius-md)] px-3 py-2 ${
                m.role === "user"
                  ? "bg-[var(--primary-muted)] text-[var(--text-primary)]"
                  : "bg-[var(--surface-base)] text-[var(--text-secondary)]"
              }`}
            >
              {m.text}
            </div>
            {m.blocks && m.role === "assistant" && (
              <GenUiRenderer
                blocks={m.blocks}
                onApplyJob={onApplyJob}
                onAction={handleAction}
                onFilterChip={onFilter}
              />
            )}
          </div>
        ))}
        {streaming && (
          <div className="flex items-center gap-2 text-[var(--text-disabled)] text-xs">
            <Loader2 size={14} className="animate-spin" /> {copy.jobs.copilotThinking}
          </div>
        )}
      </div>

      <div className="px-3 pb-2 flex flex-wrap gap-1">
        {STARTERS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => send(s)}
            className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--surface-base)] hover:bg-[var(--primary-muted)] border border-[var(--border-subtle)] text-[var(--text-secondary)]"
          >
            {s}
          </button>
        ))}
      </div>

      <div className="p-3 border-t border-[var(--border-subtle)]">
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={send}
          placeholder={copy.jobs.copilotPlaceholder}
          streaming={streaming}
        />
      </div>
    </div>
  );
}

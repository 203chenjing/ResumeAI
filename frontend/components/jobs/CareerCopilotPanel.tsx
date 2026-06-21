"use client";

import { useState } from "react";
import { Bot, Loader2, Send, X } from "lucide-react";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import type { CareerCopilotEvent, GenUiBlock } from "@/lib/types";
import GenUiRenderer from "@/components/jobs/GenUiRenderer";

type Message = { role: "user" | "assistant"; text: string; blocks?: GenUiBlock[] };

const STARTERS = [
  "推荐最匹配我简历的秋招岗位",
  "今天有哪些 P0 优先投递？",
  "北京秋招岗位有哪些？",
  "帮我刷新并同步飞书表",
];

type Props = {
  onApplyJob: (jobId: string) => void;
  onCrawl: () => void;
  onSyncFeishu: () => void;
  onFilter: (q: string) => void;
  onCompare: (ids: string[]) => void;
};

export default function CareerCopilotPanel({
  onApplyJob,
  onCrawl,
  onSyncFeishu,
  onFilter,
  onCompare,
}: Props) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      text: "我是求职 Copilot：可以说自然语言，我会用混合匹配（BM25+技能图谱）生成可点的岗位卡片。",
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
    if (action === "sync_feishu") onSyncFeishu();
    if (action === "compare" && payload?.job_ids) onCompare(payload.job_ids as string[]);
    if (action === "navigate" && payload?.path) window.location.href = String(payload.path);
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2 px-4 py-3 rounded-full shadow-lg bg-violet-600 text-white text-sm hover:bg-violet-700"
      >
        <Bot size={18} /> 求职 Copilot
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-40 w-[min(420px,calc(100vw-2rem))] flex flex-col rounded-2xl border shadow-2xl bg-white overflow-hidden max-h-[min(640px,calc(100vh-4rem))]">
      <div className="flex items-center justify-between px-4 py-3 border-b bg-gradient-to-r from-violet-600 to-indigo-600 text-white">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Bot size={18} /> 求职 Copilot · LUI + GUI
        </div>
        <button type="button" onClick={() => setOpen(false)} className="p-1 hover:bg-white/20 rounded">
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3 text-sm">
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : ""}>
            <div
              className={`inline-block max-w-[95%] rounded-xl px-3 py-2 ${
                m.role === "user" ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-800"
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
          <div className="flex items-center gap-2 text-slate-400 text-xs">
            <Loader2 size={14} className="animate-spin" /> 生成界面…
          </div>
        )}
      </div>

      <div className="px-3 pb-2 flex flex-wrap gap-1">
        {STARTERS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => send(s)}
            className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 hover:bg-violet-100 border"
          >
            {s}
          </button>
        ))}
      </div>

      <form
        className="flex gap-2 p-3 border-t"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="例如：推荐最匹配的 AI 产品岗"
          className="flex-1 text-sm border rounded-lg px-3 py-2"
        />
        <button
          type="submit"
          disabled={streaming}
          className="p-2 rounded-lg bg-violet-600 text-white disabled:opacity-50"
        >
          {streaming ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
        </button>
      </form>
    </div>
  );
}

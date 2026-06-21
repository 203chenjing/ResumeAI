"use client";

import { Bot, Loader2, Send } from "lucide-react";
import { ReactNode, useState } from "react";

export interface CopilotMessage {
  role: "user" | "assistant";
  content: string;
  actions?: { id: string; label: string }[];
}

type Props = {
  mode: "knowledge" | "edit";
  contextLabel?: string;
  messages: CopilotMessage[];
  quickChips?: string[];
  placeholder?: string;
  streaming?: boolean;
  onSend: (text: string) => void;
  onQuickChip?: (chip: string) => void;
  onMessageAction?: (actionId: string) => void;
  footer?: ReactNode;
};

export default function CopilotPanel({
  mode,
  contextLabel,
  messages,
  quickChips = [],
  placeholder = "输入指令…",
  streaming = false,
  onSend,
  onQuickChip,
  onMessageAction,
  footer,
}: Props) {
  const [input, setInput] = useState("");

  function submit() {
    const t = input.trim();
    if (!t || streaming) return;
    setInput("");
    onSend(t);
  }

  return (
    <div className="h-full flex flex-col bg-[var(--surface-container)] border-l border-[var(--border-subtle)]">
      <div className="shrink-0 px-3 py-2 border-b border-[var(--border-subtle)]">
        <div className="flex items-center gap-2 text-sm font-medium text-[var(--text-primary)]">
          <Bot size={16} className="text-[var(--primary)]" />
          {mode === "knowledge" ? "知识库 Copilot" : "改稿 Copilot"}
        </div>
        {contextLabel && (
          <div className="mt-1 text-xs px-2 py-0.5 rounded-full bg-[var(--surface-base)] text-[var(--text-secondary)] inline-block truncate max-w-full">
            {contextLabel}
          </div>
        )}
      </div>

      {quickChips.length > 0 && (
        <div className="shrink-0 px-2 py-2 flex flex-wrap gap-1 border-b border-[var(--border-subtle)]">
          {quickChips.map((chip) => (
            <button
              key={chip}
              type="button"
              disabled={streaming}
              onClick={() => (onQuickChip ? onQuickChip(chip) : onSend(chip))}
              className="text-xs px-2 py-1 rounded-full border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--surface-base)] disabled:opacity-50"
            >
              {chip}
            </button>
          ))}
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-3 min-h-0">
        {messages.length === 0 && (
          <p className="text-xs text-[var(--text-disabled)] leading-relaxed">
            {mode === "knowledge"
              ? "可导入简历事实、补全 STAR、检查待确认项。"
              : "可要求压缩一页、加强关键词或前往导出。"}
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`text-sm rounded-lg px-3 py-2 ${
              m.role === "user"
                ? "bg-[var(--primary)]/10 text-[var(--text-primary)] ml-4"
                : "bg-[var(--surface-base)] text-[var(--text-secondary)] mr-2"
            }`}
          >
            <div className="whitespace-pre-wrap">{m.content}</div>
            {m.role === "assistant" && m.actions && m.actions.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2 pt-2 border-t border-[var(--border-subtle)]">
                {m.actions.map((a) => (
                  <button
                    key={a.id}
                    type="button"
                    disabled={streaming}
                    onClick={() => onMessageAction?.(a.id)}
                    className="text-xs px-2.5 py-1 rounded-full bg-[var(--primary)]/10 text-[var(--primary)] hover:bg-[var(--primary)]/20 disabled:opacity-50"
                  >
                    {a.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {streaming && (
          <div className="flex items-center gap-2 text-xs text-[var(--text-disabled)]">
            <Loader2 size={12} className="animate-spin" /> 思考中…
          </div>
        )}
      </div>

      {footer}

      <div className="shrink-0 p-2 border-t border-[var(--border-subtle)]">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && submit()}
            placeholder={placeholder}
            disabled={streaming}
            className="flex-1 text-sm px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-base)] outline-none focus:ring-1 focus:ring-[var(--primary)]"
          />
          <button
            type="button"
            onClick={submit}
            disabled={streaming || !input.trim()}
            className="p-2 rounded-lg bg-[var(--primary)] text-white disabled:opacity-50"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

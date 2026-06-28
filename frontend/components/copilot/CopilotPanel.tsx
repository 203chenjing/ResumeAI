"use client";

import { Sparkles, Loader2 } from "lucide-react";
import ChatInput from "@/components/ui/ChatInput";
import { ReactNode, useState } from "react";
import { copy } from "@/lib/copy";

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
  placeholder,
  streaming = false,
  onSend,
  onQuickChip,
  onMessageAction,
  footer,
}: Props) {
  const [input, setInput] = useState("");
  const title = mode === "knowledge" ? copy.knowledge.copilotTitle : copy.edit.assistant;
  const emptyHint = mode === "knowledge" ? copy.knowledge.copilotIntro : copy.edit.assistantHint;

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
          <Sparkles size={16} className="text-[var(--primary)]" />
          {title}
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
          <p className="text-xs text-[var(--text-disabled)] leading-relaxed">{emptyHint}</p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`text-sm rounded-lg px-3 py-2 ${
              m.role === "user"
                ? "bg-[var(--primary-muted)] text-[var(--text-primary)] ml-4"
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
                    className="text-xs px-2.5 py-1 rounded-full bg-[var(--primary-muted)] text-[var(--primary)] hover:opacity-90 disabled:opacity-50"
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
            <Loader2 size={12} className="animate-spin" /> {copy.copilot.thinking}
          </div>
        )}
      </div>

      {footer}

      <div className="shrink-0 p-3 border-t border-[var(--border-subtle)]">
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={() => submit()}
          placeholder={placeholder || copy.copilot.sendPlaceholder}
          streaming={streaming}
        />
      </div>
    </div>
  );
}

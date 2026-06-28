"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Loader2, Send } from "lucide-react";
import clsx from "clsx";

const LINE_HEIGHT_PX = 22;
const MAX_ROWS = 6;

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSend: (text: string) => void;
  placeholder?: string;
  disabled?: boolean;
  streaming?: boolean;
  className?: string;
  /** Wrap in <form> and submit on Enter */
  asForm?: boolean;
};

export default function ChatInput({
  value,
  onChange,
  onSend,
  placeholder,
  disabled = false,
  streaming = false,
  className,
  asForm = false,
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const composingRef = useRef(false);
  const [isComposing, setIsComposing] = useState(false);

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const maxHeight = LINE_HEIGHT_PX * MAX_ROWS + 20;
    const next = Math.min(el.scrollHeight, maxHeight);
    el.style.height = `${next}px`;
    el.style.overflowY = el.scrollHeight > maxHeight ? "auto" : "hidden";
  }, []);

  useEffect(() => {
    adjustHeight();
  }, [value, adjustHeight]);

  function trySend() {
    const text = value.trim();
    if (!text || disabled || streaming) return;
    onSend(text);
    requestAnimationFrame(adjustHeight);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !composingRef.current && !isComposing) {
      e.preventDefault();
      trySend();
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    trySend();
  }

  const inputArea = (
    <div className={clsx("flex items-end gap-2", className)}>
      <textarea
        ref={textareaRef}
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        onCompositionStart={() => {
          composingRef.current = true;
          setIsComposing(true);
        }}
        onCompositionEnd={() => {
          composingRef.current = false;
          setIsComposing(false);
        }}
        placeholder={placeholder}
        disabled={disabled || streaming}
        className="flex-1 input-field resize-none leading-[22px] min-h-[42px] max-h-[152px] py-2.5"
        aria-label={placeholder}
      />
      <button
        type={asForm ? "submit" : "button"}
        onClick={asForm ? undefined : trySend}
        disabled={disabled || streaming || !value.trim()}
        className="shrink-0 p-2.5 rounded-[var(--radius-sm)] bg-[var(--primary)] text-white disabled:opacity-40 hover:opacity-90 transition-opacity"
        aria-label="发送"
      >
        {streaming ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
      </button>
    </div>
  );

  if (asForm) {
    return <form onSubmit={onSubmit}>{inputArea}</form>;
  }

  return inputArea;
}

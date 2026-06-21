"use client";

import { AlertTriangle, X } from "lucide-react";
import { copy } from "@/lib/copy";

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "确认",
  cancelLabel = "取消",
  variant = "warning",
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "warning" | "danger";
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/40">
      <div className="bg-[var(--surface-container)] rounded-xl shadow-xl max-w-md w-full p-6 relative">
        <button
          type="button"
          onClick={onCancel}
          className="absolute top-3 right-3 text-[var(--text-disabled)] hover:text-[var(--text-secondary)]"
          aria-label={copy.common.close}
        >
          <X size={18} />
        </button>
        <div className="flex items-start gap-3">
          <AlertTriangle
            size={22}
            className={variant === "danger" ? "text-[var(--semantic-danger)] shrink-0" : "text-[var(--semantic-warning)] shrink-0"}
          />
          <div>
            <h3 className="font-semibold text-[var(--text-primary)] mb-2">{title}</h3>
            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{message}</p>
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button type="button" onClick={onCancel} className="btn-secondary px-4 py-2">
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`px-4 py-2 text-sm rounded-lg text-white ${
              variant === "danger"
                ? "bg-[var(--semantic-danger)] hover:opacity-90"
                : "bg-[var(--semantic-warning)] hover:opacity-90"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

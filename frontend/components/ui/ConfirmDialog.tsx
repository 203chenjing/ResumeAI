"use client";

import { AlertTriangle, X } from "lucide-react";

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
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 relative">
        <button
          type="button"
          onClick={onCancel}
          className="absolute top-3 right-3 text-slate-400 hover:text-slate-600"
          aria-label="关闭"
        >
          <X size={18} />
        </button>
        <div className="flex items-start gap-3">
          <AlertTriangle
            size={22}
            className={variant === "danger" ? "text-red-500 shrink-0" : "text-amber-500 shrink-0"}
          />
          <div>
            <h3 className="font-semibold text-slate-900 mb-2">{title}</h3>
            <p className="text-sm text-slate-600 leading-relaxed">{message}</p>
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 text-sm rounded-lg border border-slate-300 hover:bg-slate-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`px-4 py-2 text-sm rounded-lg text-white ${
              variant === "danger" ? "bg-red-600 hover:bg-red-700" : "bg-amber-600 hover:bg-amber-700"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

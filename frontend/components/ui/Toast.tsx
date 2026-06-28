"use client";

import { useEffect } from "react";
import { X, CheckCircle2, AlertTriangle, Info, AlertCircle } from "lucide-react";
import { useAppStore, ToastItem } from "@/stores/useAppStore";
import clsx from "clsx";

const ICONS = {
  success: CheckCircle2,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const STYLES = {
  success: "alert-success",
  error: "alert-error",
  warning: "alert-warning",
  info: "alert-info",
};

export default function ToastContainer() {
  const { toasts, dismissToast } = useAppStore();

  return (
    <div className="snackbar-host">
      {toasts.map((t) => (
        <ToastCard key={t.id} item={t} onDismiss={() => dismissToast(t.id)} />
      ))}
    </div>
  );
}

function ToastCard({ item, onDismiss }: { item: ToastItem; onDismiss: () => void }) {
  const Icon = ICONS[item.type];

  useEffect(() => {
    if (item.duration <= 0) return;
    const timer = setTimeout(onDismiss, item.duration);
    return () => clearTimeout(timer);
  }, [item.duration, onDismiss]);

  return (
    <div
      className={clsx(
        "pointer-events-auto flex items-start gap-2 px-4 py-3 rounded-[var(--radius-md)] border text-sm",
        STYLES[item.type]
      )}
      style={{ boxShadow: "var(--shadow-md)" }}
      role="alert"
    >
      <Icon size={18} className="flex-shrink-0 mt-0.5" />
      <div className="flex-1 leading-relaxed">{item.message}</div>
      <button onClick={onDismiss} className="opacity-60 hover:opacity-100 flex-shrink-0" aria-label="关闭">
        <X size={16} />
      </button>
    </div>
  );
}

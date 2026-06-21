"use client";

import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";

export type ThinkStep = {
  id: string;
  label: string;
  status: "pending" | "running" | "done" | "error";
  detail?: string;
};

export default function ThinkChainPanel({
  title,
  steps,
  running,
}: {
  title: string;
  steps: ThinkStep[];
  running?: boolean;
}) {
  if (!steps.length) return null;

  return (
    <section className="section-card">
      <div className="flex items-center gap-2 mb-4">
        <h2 className="text-sm font-medium text-[var(--text-primary)]">{title}</h2>
        {running && <Loader2 size={14} className="animate-spin text-[var(--primary)]" />}
      </div>
      <ol className="space-y-1">
        {steps.map((s) => (
          <li key={s.id} className="flex items-start gap-3 py-2">
            <StepIcon status={s.status} />
            <div className="min-w-0 flex-1 pt-0.5">
              <div
                className={
                  s.status === "pending"
                    ? "text-sm text-[var(--text-disabled)]"
                    : "text-sm font-medium text-[var(--text-primary)]"
                }
              >
                {s.label}
              </div>
              {s.detail && (
                <div className="text-xs text-[var(--text-secondary)] mt-0.5">{s.detail}</div>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function StepIcon({ status }: { status: ThinkStep["status"] }) {
  if (status === "running") {
    return <Loader2 size={16} className="shrink-0 animate-spin text-[var(--primary)]" />;
  }
  if (status === "done") {
    return <CheckCircle2 size={16} className="shrink-0 text-[var(--semantic-success)]" />;
  }
  if (status === "error") {
    return <XCircle size={16} className="shrink-0 text-[var(--semantic-danger)]" />;
  }
  return <Circle size={16} className="shrink-0 text-[var(--text-disabled)]" />;
}

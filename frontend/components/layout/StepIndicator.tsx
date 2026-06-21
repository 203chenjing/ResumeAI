"use client";

import { Check } from "lucide-react";
import clsx from "clsx";
import { copy } from "@/lib/copy";

export default function StepIndicator({ current }: { current: 1 | 2 | 3 }) {
  const steps = [
    { id: 1, label: copy.nav.steps.prepare },
    { id: 2, label: copy.nav.steps.edit },
    { id: 3, label: copy.nav.steps.export },
  ];
  return (
    <div className="flex items-center gap-3">
      {steps.map((s, i) => {
        const done = current > s.id;
        const active = current === s.id;
        return (
          <div key={s.id} className="flex items-center gap-3">
            <div
              className={clsx(
                "w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold",
                done && "bg-[var(--semantic-success)] text-white",
                active && "bg-[var(--primary)] text-white",
                !done && !active && "bg-[var(--surface-base)] text-[var(--text-disabled)]"
              )}
            >
              {done ? <Check size={16} /> : s.id}
            </div>
            <span
              className={clsx(
                "text-sm",
                active ? "text-[var(--text-primary)] font-medium" : "text-[var(--text-secondary)]"
              )}
            >
              {s.label}
            </span>
            {i < steps.length - 1 && <div className="w-8 h-px bg-[var(--border-subtle)]" />}
          </div>
        );
      })}
    </div>
  );
}

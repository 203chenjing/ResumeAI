"use client";

import { Check } from "lucide-react";
import clsx from "clsx";

export default function StepIndicator({ current }: { current: 1 | 2 | 3 }) {
  const steps = [
    { id: 1, label: "上传简历 / JD" },
    { id: 2, label: "AI 修改建议" },
    { id: 3, label: "导出 PDF" },
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
                done && "bg-green-500 text-white",
                active && "bg-blue-600 text-white",
                !done && !active && "bg-slate-200 text-slate-500"
              )}
            >
              {done ? <Check size={16} /> : s.id}
            </div>
            <span className={clsx("text-sm", active ? "text-slate-900 font-medium" : "text-slate-500")}>
              {s.label}
            </span>
            {i < steps.length - 1 && <div className="w-8 h-px bg-slate-300" />}
          </div>
        );
      })}
    </div>
  );
}

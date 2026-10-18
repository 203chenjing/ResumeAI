"use client";

import { useEffect, useState } from "react";
import { Gauge } from "lucide-react";
import { api } from "@/lib/api";
import { copy } from "@/lib/copy";
import type { LayoutMetrics } from "@/lib/types";
import clsx from "clsx";

/**
 * 改稿页常驻容量仪表。
 *
 * 设计意图：把「一页」这个约束从定稿环节的判决书，变成编辑时就看得见的预算。
 * 指标由后端按「规范化后」的正文计算，与定稿/导出口径一致。
 */
export default function CapacityMeter({
  sessionId,
  markdown,
  onOpenExport,
}: {
  sessionId: string;
  markdown: string;
  onOpenExport?: () => void;
}) {
  const [metrics, setMetrics] = useState<LayoutMetrics | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      api
        .layoutMetrics(sessionId)
        .then((res) => {
          if (!cancelled && res.success && res.data) setMetrics(res.data);
        })
        .catch(() => {});
    }, 500);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [sessionId, markdown]);

  if (!metrics) return null;

  const overCapacity = metrics.capacity_pct >= 100;
  const nearCapacity = metrics.capacity_pct >= 85;
  const itemsOver = metrics.experience_items > metrics.experience_limit;
  const skillsOver = metrics.skill_items !== metrics.skill_limit;

  const tone = overCapacity
    ? "text-[var(--semantic-warning)] border-[var(--semantic-warning)]/40"
    : nearCapacity
      ? "text-[var(--text-primary)] border-[var(--border-subtle)]"
      : "text-[var(--text-secondary)] border-[var(--border-subtle)]";

  return (
    <button
      type="button"
      onClick={onOpenExport}
      title={overCapacity ? copy.capacity.overflow : copy.capacity.ok}
      className={clsx(
        "hidden md:inline-flex items-center gap-2 rounded-[var(--radius-full)] border px-2.5 py-1 text-xs transition-colors hover:border-[var(--primary)]/50",
        tone
      )}
    >
      <Gauge size={13} />
      <span className="tabular-nums">{copy.capacity.label}</span>
      <span
        className="inline-block h-1.5 w-14 overflow-hidden rounded-full bg-[var(--surface-base)]"
        aria-hidden
      >
        <span
          className={clsx(
            "block h-full rounded-full",
            overCapacity
              ? "bg-[var(--semantic-warning)]"
              : nearCapacity
                ? "bg-[var(--primary)]"
                : "bg-[var(--semantic-success)]"
          )}
          style={{ width: `${Math.max(4, Math.min(100, metrics.capacity_pct))}%` }}
        />
      </span>
      <span className={clsx("tabular-nums", overCapacity && "font-medium")}>
        {copy.capacity.pages(metrics.estimated_pages)}
      </span>
      <span className={clsx("tabular-nums", itemsOver && "text-[var(--semantic-warning)]")}>
        {copy.capacity.items(metrics.experience_items, metrics.experience_limit)}
      </span>
      <span className={clsx("tabular-nums", skillsOver && "text-[var(--semantic-warning)]")}>
        {copy.capacity.skills(metrics.skill_items, metrics.skill_limit)}
      </span>
    </button>
  );
}

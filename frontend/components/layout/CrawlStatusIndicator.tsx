"use client";

import Link from "next/link";
import { Loader2 } from "lucide-react";
import { copy } from "@/lib/copy";
import { ROUTES } from "@/lib/navigation";
import { useCrawlStore } from "@/stores/useCrawlStore";

/** 顶栏下 2px 进度线（Gmail / Drive 式，不抢主任务注意力） */
export function CrawlStatusLine() {
  const status = useCrawlStore((s) => s.status);
  if (status !== "running") return null;

  return (
    <div
      className="h-0.5 w-full shrink-0 bg-[var(--border-faint)] overflow-hidden"
      aria-hidden
    >
      <div className="crawl-indeterminate-bar h-full w-1/4 bg-[var(--primary)] opacity-50" />
    </div>
  );
}

/** 顶栏右侧轻量状态（渐进披露：仅运行中 / 刚完成 / 出错时显示） */
export function CrawlStatusChip() {
  const status = useCrawlStore((s) => s.status);
  const progress = useCrawlStore((s) => s.progress);
  const error = useCrawlStore((s) => s.error);
  const dismiss = useCrawlStore((s) => s.dismiss);

  if (status === "idle") return null;

  if (status === "running") {
    return (
      <span
        className="inline-flex items-center gap-1.5 max-w-[11rem] sm:max-w-xs text-xs text-[var(--text-secondary)] truncate"
        role="status"
        aria-live="polite"
        title={progress || copy.crawl.running}
      >
        <Loader2 size={12} className="shrink-0 animate-spin opacity-60" aria-hidden />
        <span className="truncate">{progress || copy.crawl.running}</span>
      </span>
    );
  }

  if (status === "done") {
    return (
      <Link
        href={ROUTES.jobs}
        className="inline-flex items-center gap-1 text-xs text-[var(--semantic-success)] hover:underline truncate max-w-[10rem] sm:max-w-xs"
        role="status"
      >
        <span className="truncate">{progress || copy.crawl.done}</span>
      </Link>
    );
  }

  return (
    <button
      type="button"
      onClick={dismiss}
      className="inline-flex items-center gap-1 text-xs text-[var(--semantic-warning)] hover:underline truncate max-w-[10rem] sm:max-w-xs text-left"
      title={copy.crawl.dismiss}
    >
      <span className="truncate">{error || copy.crawl.failed}</span>
    </button>
  );
}

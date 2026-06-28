"use client";

import Link from "next/link";
import { copy } from "@/lib/copy";
import { ROUTES } from "@/lib/navigation";
import { useCrawlStore } from "@/stores/useCrawlStore";

/** 后台爬虫耗时较长，不在全局布局展示持续动画。 */
export function CrawlStatusLine() {
  return null;
}

/** 顶栏右侧低调状态：仅提示后台任务存在，不使用持续动画。 */
export function CrawlStatusChip() {
  const status = useCrawlStore((s) => s.status);
  const progress = useCrawlStore((s) => s.progress);
  const error = useCrawlStore((s) => s.error);
  const dismiss = useCrawlStore((s) => s.dismiss);

  if (status === "idle") return null;

  if (status === "running") {
    return (
      <Link
        href={ROUTES.jobs}
        className="hidden sm:inline-flex items-center max-w-[9rem] text-[11px] text-[var(--text-disabled)] hover:text-[var(--text-secondary)] truncate"
        role="status"
        aria-live="polite"
        title={progress || copy.crawl.running}
      >
        <span className="truncate">岗位库更新中</span>
      </Link>
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

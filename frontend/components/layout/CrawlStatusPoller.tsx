"use client";

import { useEffect } from "react";
import { api } from "@/lib/api";
import { copy } from "@/lib/copy";
import { getClientId } from "@/lib/userMemory";
import { useCrawlStore, type CrawlResultPayload } from "@/stores/useCrawlStore";

function formatDoneMessage(data: CrawlResultPayload): string {
  if (data.new_count == null || data.total == null) return copy.crawl.done;
  const ok = data.quality?.validated_ok;
  const extra = ok != null ? copy.crawl.doneWithQuality(ok) : "";
  return copy.crawl.doneWithCount(data.new_count, data.total, extra);
}

/** 全局轮询后台爬虫，任意页面可感知状态 */
export default function CrawlStatusPoller() {
  const status = useCrawlStore((s) => s.status);
  const doneAt = useCrawlStore((s) => s.doneAt);
  const setRunning = useCrawlStore((s) => s.setRunning);
  const setDone = useCrawlStore((s) => s.setDone);
  const setError = useCrawlStore((s) => s.setError);
  const dismiss = useCrawlStore((s) => s.dismiss);

  // 完成 / 错误提示自动收起（Material：短暂确认，不常驻）
  useEffect(() => {
    if (status !== "done" && status !== "error") return;
    if (!doneAt) return;
    const elapsed = Date.now() - doneAt;
    const delay = Math.max(0, 4500 - elapsed);
    const t = window.setTimeout(() => dismiss(), delay);
    return () => window.clearTimeout(t);
  }, [status, doneAt, dismiss]);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;

    const schedule = (ms: number) => {
      if (!active) return;
      timer = window.setTimeout(tick, ms);
    };

    async function tick() {
      if (!active) return;
      try {
        const res = await api.getCrawlStatus(getClientId());
        const data = res.data;
        if (!active || !res.success || !data) {
          schedule(15000);
          return;
        }

        if (data.status === "running") {
          setRunning(data.progress || copy.crawl.running);
          schedule(2500);
          return;
        }

        if (data.status === "done") {
          const payload: CrawlResultPayload = {
            new_count: data.new_count,
            total: data.total,
            quality: data.quality,
            jobs: data.jobs,
            digest: data.digest,
            crawl_health: data.crawl_health,
          };
          setDone(formatDoneMessage(payload), payload);
          schedule(15000);
          return;
        }

        if (data.status === "error") {
          setError(data.error || copy.crawl.failed);
          schedule(15000);
          return;
        }

        if (useCrawlStore.getState().status === "running") {
          dismiss();
        }
        schedule(15000);
      } catch {
        schedule(8000);
      }
    }

    tick();
    return () => {
      active = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [setRunning, setDone, setError, dismiss]);

  return null;
}

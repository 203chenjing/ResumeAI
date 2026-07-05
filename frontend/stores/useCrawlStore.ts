import { create } from "zustand";
import type { CrawlHealth, JobDigest, JobPosting } from "@/lib/types";

export type CrawlUiStatus = "idle" | "running" | "done" | "error";

export interface CrawlResultPayload {
  new_count?: number;
  total?: number;
  quality?: { validated_ok?: number };
  jobs?: JobPosting[];
  digest?: JobDigest;
  crawl_health?: CrawlHealth;
}

interface CrawlState {
  status: CrawlUiStatus;
  progress: string;
  error: string;
  /** 增量刷新时的中间态 */
  partialTotal: number;
  partialNew: number;
  providerIndex: number;
  providerTotal: number;
  /** 完成后供岗位页消费一次 */
  lastResult: CrawlResultPayload | null;
  /** 用于自动收起「已完成」提示 */
  doneAt: number | null;
  setRunning: (progress?: string) => void;
  setProgress: (progress: string, partial?: { total?: number; new_count?: number; provider_index?: number; provider_total?: number }) => void;
  setDone: (progress: string, result?: CrawlResultPayload) => void;
  setError: (message: string) => void;
  consumeLastResult: () => CrawlResultPayload | null;
  dismiss: () => void;
}

export const useCrawlStore = create<CrawlState>((set, get) => ({
  status: "idle",
  progress: "",
  error: "",
  partialTotal: 0,
  partialNew: 0,
  providerIndex: 0,
  providerTotal: 0,
  lastResult: null,
  doneAt: null,

  setRunning: (progress = "") =>
    set({
      status: "running",
      progress,
      error: "",
      doneAt: null,
      lastResult: null,
      partialTotal: 0,
      partialNew: 0,
      providerIndex: 0,
      providerTotal: 0,
    }),

  setProgress: (progress, partial) =>
    set({
      progress,
      partialTotal: partial?.total ?? get().partialTotal,
      partialNew: partial?.new_count ?? get().partialNew,
      providerIndex: partial?.provider_index ?? get().providerIndex,
      providerTotal: partial?.provider_total ?? get().providerTotal,
    }),

  setDone: (progress, result) =>
    set({
      status: "done",
      progress,
      error: "",
      lastResult: result ?? null,
      doneAt: Date.now(),
    }),

  setError: (message) =>
    set({ status: "error", error: message, doneAt: Date.now() }),

  consumeLastResult: () => {
    const payload = get().lastResult;
    if (payload) set({ lastResult: null });
    return payload;
  },

  dismiss: () =>
    set({
      status: "idle",
      progress: "",
      error: "",
      doneAt: null,
      partialTotal: 0,
      partialNew: 0,
      providerIndex: 0,
      providerTotal: 0,
    }),
}));

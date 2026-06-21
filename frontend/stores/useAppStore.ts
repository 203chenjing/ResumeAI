import { create } from "zustand";
import {
  ChatMessage,
  JDAnalysis,
  JobPosting,
  MatchResult,
  ParsedResume,
  Suggestion,
} from "@/lib/types";

interface AppState {
  // 会话
  sessionId: string;
  setSessionId: (id: string) => void;

  // 简历
  parsedResume: ParsedResume | null;
  setParsedResume: (r: ParsedResume | null) => void;
  originalMarkdown: string;
  setOriginalMarkdown: (md: string) => void;
  currentMarkdown: string;
  setCurrentMarkdown: (md: string) => void;
  finalizedMarkdown: string;
  setFinalizedMarkdown: (md: string) => void;
  finalizeStatus: FinalizeStatus;
  setFinalizeStatus: (s: FinalizeStatus) => void;

  // JD
  jdText: string;
  setJdText: (t: string) => void;
  jdAnalysis: JDAnalysis | null;
  setJdAnalysis: (a: JDAnalysis | null) => void;

  // 匹配
  matchResult: MatchResult | null;
  setMatchResult: (m: MatchResult | null) => void;

  // 建议
  suggestions: Suggestion[];
  setSuggestions: (list: Suggestion[]) => void;
  upsertSuggestion: (s: Suggestion) => void;
  appendSuggestions: (list: Suggestion[]) => void;
  mergeSuggestions: (list: Suggestion[]) => void;
  filter: "all" | "pending" | "accepted" | "rejected";
  setFilter: (f: AppState["filter"]) => void;
  highlightSuggestionIds: string[];
  setHighlightSuggestionIds: (ids: string[]) => void;

  // 聊天
  chatMessages: ChatMessage[];
  appendChat: (m: ChatMessage) => void;
  updateLastAssistant: (chunk: string) => void;
  setLastAssistant: (content: string) => void;
  resetChat: () => void;

  // 知识库
  knowledgeBase: string;
  setKnowledgeBase: (t: string) => void;

  studioFromJob: JobPosting | null;
  setStudioFromJob: (j: JobPosting | null) => void;
  copilotOpen: boolean;
  setCopilotOpen: (v: boolean) => void;

  // 内容密度
  density: DensityInfo | null;
  setDensity: (d: DensityInfo | null) => void;

  // 通知
  toasts: ToastItem[];
  pushToast: (message: string, type?: ToastItem["type"], duration?: number) => void;
  dismissToast: (id: string) => void;

  // 全局加载
  loading: boolean;
  setLoading: (b: boolean) => void;

  reset: () => void;
}

export type FinalizeStatus = "draft" | "finalized" | "stale";

export interface DensityInfo {
  char_count: number;
  status: "sparse" | "light" | "ok" | "dense";
  message: string;
}

export interface ToastItem {
  id: string;
  message: string;
  type: "success" | "error" | "warning" | "info";
  duration: number;
}

export const useAppStore = create<AppState>((set) => ({
  sessionId: "",
  setSessionId: (id) => set({ sessionId: id }),

  parsedResume: null,
  setParsedResume: (r) => set({ parsedResume: r }),
  originalMarkdown: "",
  setOriginalMarkdown: (md) => set({ originalMarkdown: md }),
  currentMarkdown: "",
  setCurrentMarkdown: (md) => set({ currentMarkdown: md }),
  finalizedMarkdown: "",
  setFinalizedMarkdown: (md) => set({ finalizedMarkdown: md }),
  finalizeStatus: "draft",
  setFinalizeStatus: (s) => set({ finalizeStatus: s }),

  jdText: "",
  setJdText: (t) => set({ jdText: t }),
  jdAnalysis: null,
  setJdAnalysis: (a) => set({ jdAnalysis: a }),

  matchResult: null,
  setMatchResult: (m) => set({ matchResult: m }),

  suggestions: [],
  setSuggestions: (list) => set({ suggestions: list }),
  upsertSuggestion: (s) =>
    set((state) => ({
      suggestions: state.suggestions.some((x) => x.id === s.id)
        ? state.suggestions.map((x) => (x.id === s.id ? s : x))
        : [...state.suggestions, s],
    })),
  appendSuggestions: (list) =>
    set((state) => ({ suggestions: [...state.suggestions, ...list] })),
  mergeSuggestions: (list) =>
    set((state) => {
      const map = new Map(state.suggestions.map((s) => [s.id, s]));
      for (const s of list) map.set(s.id, s);
      return { suggestions: Array.from(map.values()) };
    }),
  filter: "all",
  setFilter: (f) => set({ filter: f }),

  highlightSuggestionIds: [] as string[],
  setHighlightSuggestionIds: (ids) => set({ highlightSuggestionIds: ids }),

  chatMessages: [],
  appendChat: (m) => set((state) => ({ chatMessages: [...state.chatMessages, m] })),
  updateLastAssistant: (chunk) =>
    set((state) => {
      const arr = [...state.chatMessages];
      const last = arr[arr.length - 1];
      if (last && last.role === "assistant") {
        arr[arr.length - 1] = { ...last, content: last.content + chunk };
      } else {
        arr.push({ role: "assistant", content: chunk });
      }
      return { chatMessages: arr };
    }),
  setLastAssistant: (content) =>
    set((state) => {
      const arr = [...state.chatMessages];
      const last = arr[arr.length - 1];
      if (last && last.role === "assistant") {
        arr[arr.length - 1] = { ...last, content };
      } else {
        arr.push({ role: "assistant", content });
      }
      return { chatMessages: arr };
    }),
  resetChat: () => set({ chatMessages: [] }),

  knowledgeBase: "",
  setKnowledgeBase: (t) => set({ knowledgeBase: t }),

  studioFromJob: null,
  setStudioFromJob: (j) => set({ studioFromJob: j }),
  copilotOpen: true,
  setCopilotOpen: (v) => set({ copilotOpen: v }),

  density: null,
  setDensity: (d) => set({ density: d }),

  toasts: [],
  pushToast: (message, type = "info", duration = 5000) =>
    set((state) => ({
      toasts: [
        ...state.toasts,
        { id: `${Date.now()}-${Math.random()}`, message, type, duration },
      ],
    })),
  dismissToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),

  loading: false,
  setLoading: (b) => set({ loading: b }),

  reset: () =>
    set({
      sessionId: "",
      parsedResume: null,
      originalMarkdown: "",
      currentMarkdown: "",
      finalizedMarkdown: "",
      finalizeStatus: "draft",
      jdText: "",
      jdAnalysis: null,
      matchResult: null,
      suggestions: [],
      chatMessages: [],
      knowledgeBase: "",
      studioFromJob: null,
      copilotOpen: true,
      density: null,
      toasts: [],
      filter: "all",
      loading: false,
      highlightSuggestionIds: [],
    }),
}));

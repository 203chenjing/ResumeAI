import { api } from "./api";
import type {
  ChatMessage,
  JDAnalysis,
  MatchResult,
  ParsedResume,
  Suggestion,
} from "./types";
import type { ApplicationDecision } from "@/components/match/ApplicationDecision";

const SESSION_KEY = "resumeai_session_id";
const STUDIO_META_KEY = "resumeai_studio_meta";

export interface LastStudioMeta {
  sessionId: string;
  company: string;
  role: string;
  step: 1 | 2 | 3;
}

export const EMPTY_STUDIO_META: LastStudioMeta = {
  sessionId: "",
  company: "",
  role: "",
  step: 2,
};

export function getLastStudioMeta(): LastStudioMeta {
  if (typeof window === "undefined") {
    return { ...EMPTY_STUDIO_META };
  }
  try {
    const raw = localStorage.getItem(STUDIO_META_KEY);
    if (raw) return JSON.parse(raw) as LastStudioMeta;
  } catch {
    /* ignore */
  }
  const sessionId = localStorage.getItem(SESSION_KEY) || "";
  return { sessionId, company: "", role: "", step: 2 };
}

export function persistStudioMeta(meta: Partial<LastStudioMeta> & { sessionId?: string }) {
  if (typeof window === "undefined") return;
  const prev = getLastStudioMeta();
  const next: LastStudioMeta = {
    sessionId: meta.sessionId ?? prev.sessionId,
    company: meta.company ?? prev.company,
    role: meta.role ?? prev.role,
    step: meta.step ?? prev.step,
  };
  localStorage.setItem(STUDIO_META_KEY, JSON.stringify(next));
  if (next.sessionId) persistSessionId(next.sessionId);
}

export function getPersistedSessionId(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(SESSION_KEY) || "";
}

export function persistSessionId(id: string) {
  if (typeof window === "undefined" || !id) return;
  localStorage.setItem(SESSION_KEY, id);
}

export function clearPersistedSessionId() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(SESSION_KEY);
}

export interface HydratedSession {
  session_id: string;
  current_resume_md: string;
  original_resume_md?: string;
  parsed_resume?: ParsedResume;
  jd_text?: string;
  jd_analysis?: JDAnalysis;
  match_result?: MatchResult;
  suggestions?: Suggestion[];
  chat_history?: ChatMessage[];
  knowledge_base_md?: string;
  finalized_resume_md?: string;
  finalize_status?: string;
}

/** 从后端恢复会话并写入 Zustand（对标 resume-lm 持久化） */
export async function hydrateSessionFromServer(
  sessionId: string,
  setters: {
    setSessionId: (id: string) => void;
    setCurrentMarkdown: (md: string) => void;
    setOriginalMarkdown: (md: string) => void;
    setParsedResume: (r: ParsedResume | null) => void;
    setJdText: (t: string) => void;
    setJdAnalysis: (a: JDAnalysis | null) => void;
    setMatchResult: (m: MatchResult | null) => void;
    setSuggestions: (s: Suggestion[]) => void;
    setKnowledgeBase: (kb: string) => void;
    setFinalizedMarkdown: (md: string) => void;
    setFinalizeStatus: (s: "draft" | "finalized" | "stale") => void;
  }
): Promise<boolean> {
  const res = await api.getSession(sessionId);
  if (!res.success || !res.data) return false;
  const d = res.data as HydratedSession & Record<string, unknown>;

  setters.setSessionId(sessionId);
  persistSessionId(sessionId);
  if (d.current_resume_md) setters.setCurrentMarkdown(d.current_resume_md);
  if (d.original_resume_md) setters.setOriginalMarkdown(d.original_resume_md as string);
  else if (d.current_resume_md) setters.setOriginalMarkdown(d.current_resume_md);
  if (d.parsed_resume) setters.setParsedResume(d.parsed_resume as ParsedResume);
  if (d.jd_text) setters.setJdText(d.jd_text as string);
  if (d.jd_analysis) setters.setJdAnalysis(d.jd_analysis as JDAnalysis);
  if (d.match_result) setters.setMatchResult(d.match_result as MatchResult);
  if (d.suggestions) setters.setSuggestions(d.suggestions as Suggestion[]);
  if (d.knowledge_base_md) setters.setKnowledgeBase(d.knowledge_base_md as string);
  if (d.finalized_resume_md) setters.setFinalizedMarkdown(d.finalized_resume_md as string);
  if (d.finalize_status) {
    setters.setFinalizeStatus(d.finalize_status as "draft" | "finalized" | "stale");
  }
  return true;
}

export type { ApplicationDecision };

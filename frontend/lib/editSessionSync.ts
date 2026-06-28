import type { EditChatEvent } from "@/lib/api";
import type { Suggestion } from "@/lib/types";
import type { DensityInfo, FinalizeStatus } from "@/stores/useAppStore";

export interface EditUiPatch {
  filter?: "all" | "pending" | "accepted" | "rejected";
  highlight_ids?: string[];
  focus_panel?: string;
}

export interface EditSessionSetters {
  setSuggestions: (list: Suggestion[]) => void;
  mergeSuggestions: (list: Suggestion[]) => void;
  setCurrentMarkdown: (md: string) => void;
  setFinalizedMarkdown: (md: string) => void;
  setFinalizeStatus: (s: FinalizeStatus) => void;
  setMatchResult: (m: import("@/lib/types").MatchResult | null) => void;
  setDensity: (d: DensityInfo | null) => void;
  setFilter: (f: "all" | "pending" | "accepted" | "rejected") => void;
  setHighlightSuggestionIds: (ids: string[]) => void;
  setCopilotOpen?: (open: boolean) => void;
}

export function mergeSuggestionLists(
  existing: Suggestion[],
  incoming: Suggestion[]
): Suggestion[] {
  const map = new Map(existing.map((s) => [s.id, s]));
  for (const s of incoming) map.set(s.id, s);
  return Array.from(map.values());
}

/** 将 Agent done 事件同步到 Zustand，并返回 UI 反馈元数据 */
export function applyEditChatDone(
  event: EditChatEvent,
  setters: EditSessionSetters
): { newCount: number; highlightIds: string[]; pendingDelta: number } {
  if (event.type !== "done") return { newCount: 0, highlightIds: [], pendingDelta: 0 };

  const patch = (event as { ui_patch?: EditUiPatch }).ui_patch;
  const incoming = event.new_suggestions ?? [];
  const pendingBefore =
    event.session?.suggestions?.filter(
      (s) => s.status === "pending" || s.status === "adjusted"
    ).length ?? 0;

  if (event.session) {
    const s = event.session;
    if (s.suggestions) setters.setSuggestions(s.suggestions);
    if (s.current_resume_md !== undefined) setters.setCurrentMarkdown(s.current_resume_md);
    if (s.finalized_resume_md !== undefined) setters.setFinalizedMarkdown(s.finalized_resume_md);
    if (s.finalize_status) setters.setFinalizeStatus(s.finalize_status);
    if (s.match !== undefined) setters.setMatchResult(s.match);
    if (s.density) setters.setDensity(s.density as DensityInfo);
  }

  if (incoming.length > 0) {
    setters.mergeSuggestions(incoming);
  }

  const pendingAfter =
    event.session?.suggestions?.filter(
      (s) => s.status === "pending" || s.status === "adjusted"
    ).length ?? pendingBefore;
  const pendingDelta = Math.max(0, pendingAfter - pendingBefore);

  const highlightIds =
    patch?.highlight_ids?.filter(Boolean) ??
    incoming.map((s) => s.id).filter(Boolean);

  if (patch?.filter) {
    setters.setFilter(patch.filter);
  } else if (incoming.length > 0 || pendingDelta > 0) {
    setters.setFilter("pending");
  } else if (event.session?.suggestions) {
    const pending = event.session.suggestions.filter(
      (s) => s.status === "pending" || s.status === "adjusted"
    );
    if (pending.length > 0 && patch?.highlight_ids?.length) {
      setters.setFilter("pending");
    }
  }

  if (patch?.focus_panel === "suggestions") {
    setters.setFilter("pending");
    setters.setCopilotOpen?.(true);
  }

  if (highlightIds.length > 0) {
    setters.setHighlightSuggestionIds(highlightIds);
  } else if (pendingDelta > 0 && event.session?.suggestions) {
    const pending = event.session.suggestions.filter(
      (s) => s.status === "pending" || s.status === "adjusted"
    );
    setters.setHighlightSuggestionIds(pending.map((s) => s.id));
  }

  return {
    newCount: incoming.length > 0 ? incoming.length : pendingDelta,
    highlightIds,
    pendingDelta,
  };
}

export function buildEditUiContext(state: {
  filter: string;
  suggestions: Suggestion[];
}) {
  const pending = state.suggestions.filter(
    (s) => s.status === "pending" || s.status === "adjusted"
  );
  return {
    filter: state.filter,
    suggestions_total: state.suggestions.length,
    pending_count: pending.length,
    accepted_count: state.suggestions.filter((s) => s.status === "accepted").length,
    rejected_count: state.suggestions.filter((s) => s.status === "rejected").length,
    pending_ids: pending.map((s) => s.id).slice(0, 20),
    pending_items: pending.slice(0, 12).map((s) => ({
      id: s.id,
      section: s.section,
      type: s.type,
      original_preview: (s.original_text || "").slice(0, 120),
      line_range: s.line_range,
    })),
  };
}

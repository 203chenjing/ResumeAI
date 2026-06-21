import type { KnowledgeSection } from "@/lib/knowledgeSections";
import { extractPendingMarkers } from "@/lib/knowledgePending";

export interface KnowledgeUiPatch {
  focus_panel?: "topics" | "pending";
  select_section_title?: string;
  saved?: boolean;
}

export interface KnowledgeChatResult {
  reply: string;
  updated_markdown?: string | null;
  saved?: boolean;
  ui_patch?: KnowledgeUiPatch;
}

export interface KnowledgeUiContext {
  selected_section_title?: string;
  selected_section_id?: string;
  pending_count: number;
  facts_count: number;
  view_mode: string;
  left_tab: string;
}

export function buildKnowledgeUiContext(state: {
  content: string;
  selectedSection?: KnowledgeSection | null;
  viewMode: string;
  leftTab: string;
}): KnowledgeUiContext {
  return {
    selected_section_title: state.selectedSection?.title,
    selected_section_id: state.selectedSection?.id,
    pending_count: extractPendingMarkers(state.content).length,
    facts_count: (state.content.match(/^[-*]\s+\S/gm) || []).length,
    view_mode: state.viewMode,
    left_tab: state.leftTab,
  };
}

export interface KnowledgeApplyCallbacks {
  onContentChange: (md: string) => void;
  onOpenPendingWorkspace?: (focusId?: string | null) => void;
  onSelectSectionByTitle?: (title: string) => void;
  onSaved?: (md: string) => void;
}

/** 将 Copilot chat 结果应用到知识库 UI */
export function applyKnowledgeChatResult(
  result: KnowledgeChatResult,
  callbacks: KnowledgeApplyCallbacks
): { updated: boolean; saved: boolean } {
  const updatedMd = result.updated_markdown?.trim();
  const patch = result.ui_patch || {};
  let updated = false;

  if (updatedMd && updatedMd.length > 0) {
    callbacks.onContentChange(updatedMd);
    updated = true;
    if (result.saved) {
      callbacks.onSaved?.(updatedMd);
    }
  }

  if (patch.focus_panel === "pending") {
    callbacks.onOpenPendingWorkspace?.();
  }

  if (patch.select_section_title) {
    callbacks.onSelectSectionByTitle?.(patch.select_section_title);
  }

  return { updated, saved: Boolean(result.saved && updated) };
}

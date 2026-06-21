import type { KnowledgeSection } from "@/lib/knowledgeSections";
import { extractPendingMarkers } from "@/lib/knowledgePending";
import { parseKnowledgeTopics } from "@/lib/knowledgeTopics";

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

/** 对比新旧知识库，找出新增或最相关的主题标题（供左侧导航定位） */
export function findNewOrChangedTopic(oldMd: string, newMd: string): string | null {
  const oldTopics = parseKnowledgeTopics(oldMd);
  const newTopics = parseKnowledgeTopics(newMd);
  const oldTitles = new Set(oldTopics.map((t) => t.title));
  const added = newTopics.filter((t) => !oldTitles.has(t.title));
  const projectLike = added.filter(
    (t) => t.level >= 3 || /项目|实习|公司|岗位|经历/.test(t.title)
  );
  if (projectLike.length > 0) {
    return projectLike[projectLike.length - 1].title;
  }
  if (added.length > 0) {
    return added[added.length - 1].title;
  }
  const oldLen = oldMd.length;
  const newLen = newMd.length;
  if (newLen > oldLen + 40) {
    const level3 = newTopics.filter((t) => t.level === 3);
    if (level3.length > 0) return level3[level3.length - 1].title;
  }
  return null;
}

export interface KnowledgeApplyCallbacks {
  onContentChange: (md: string) => void;
  onOpenPendingWorkspace?: (focusId?: string | null) => void;
  onSelectSectionByTitle?: (title: string, md?: string) => void;
  onSaved?: (md: string) => void;
}

/** 将 Copilot chat 结果应用到知识库 UI */
export function applyKnowledgeChatResult(
  result: KnowledgeChatResult,
  callbacks: KnowledgeApplyCallbacks,
  previousContent?: string
): { updated: boolean; saved: boolean; navigatedTo?: string } {
  const updatedMd = result.updated_markdown?.trim();
  const patch = result.ui_patch || {};
  let updated = false;
  let navigatedTo: string | undefined;

  if (updatedMd && updatedMd.length > 0) {
    callbacks.onContentChange(updatedMd);
    updated = true;
    if (result.saved) {
      callbacks.onSaved?.(updatedMd);
    }

    navigatedTo =
      patch.select_section_title ||
      findNewOrChangedTopic(previousContent || "", updatedMd) ||
      undefined;

    if (navigatedTo) {
      callbacks.onSelectSectionByTitle?.(navigatedTo, updatedMd);
    } else if (patch.focus_panel === "pending") {
      callbacks.onOpenPendingWorkspace?.();
    }
  } else if (patch.focus_panel === "pending") {
    callbacks.onOpenPendingWorkspace?.();
  } else if (patch.select_section_title) {
    callbacks.onSelectSectionByTitle?.(patch.select_section_title);
    navigatedTo = patch.select_section_title;
  }

  return { updated, saved: Boolean(result.saved && updated), navigatedTo };
}

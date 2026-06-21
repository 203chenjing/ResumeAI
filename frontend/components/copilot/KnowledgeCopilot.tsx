"use client";

import { useState } from "react";
import CopilotPanel, { CopilotMessage } from "./CopilotPanel";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import { useAppStore } from "@/stores/useAppStore";
import type { KnowledgeSection } from "@/lib/knowledgeSections";
import { extractPendingMarkers } from "@/lib/knowledgePending";
import {
  applyKnowledgeChatResult,
  buildKnowledgeUiContext,
  type KnowledgeUiContext,
} from "@/lib/knowledgeSessionSync";
import { copy } from "@/lib/copy";

const QUICK_CHIPS = [
  copy.knowledge.chips.import,
  copy.knowledge.chips.star,
  copy.knowledge.chips.audit,
  copy.knowledge.chips.merge,
];

type Props = {
  content: string;
  onContentChange: (md: string) => void;
  selectedSection?: KnowledgeSection | null;
  viewMode?: string;
  leftTab?: string;
  onMergePending?: () => void;
  onOpenPendingWorkspace?: (focusId?: string | null) => void;
  onSelectSectionByTitle?: (title: string) => void;
  onAutoSaved?: (md: string) => void;
};

export default function KnowledgeCopilot({
  content,
  onContentChange,
  selectedSection,
  viewMode = "structured",
  leftTab = "topics",
  onMergePending,
  onOpenPendingWorkspace,
  onSelectSectionByTitle,
  onAutoSaved,
}: Props) {
  const { sessionId, pushToast } = useAppStore();
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [lastNavigatedTitle, setLastNavigatedTitle] = useState<string | null>(null);

  const contextLabel = selectedSection?.title || "全部主题";

  const applyCallbacks = {
    onContentChange,
    onOpenPendingWorkspace,
    onSelectSectionByTitle,
    onSaved: onAutoSaved,
  };

  function uiContext(): KnowledgeUiContext {
    return buildKnowledgeUiContext({
      content,
      selectedSection,
      viewMode,
      leftTab,
    });
  }

  async function sendMessage(text: string) {
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setStreaming(true);
    try {
      const res = await api.knowledgeAgent.chat({
        client_id: getClientId(),
        content,
        message: text,
        session_id: sessionId || "",
        ui_context: uiContext() as unknown as Record<string, unknown>,
        history: messages.slice(-6),
      });
      const data = res.data;
      const reply = data?.reply || "（无回复）";
      const { updated, saved, navigatedTo } = applyKnowledgeChatResult(
        {
          reply,
          updated_markdown: data?.updated_markdown,
          saved: data?.saved,
          ui_patch: data?.ui_patch,
        },
        applyCallbacks,
        content
      );
      if (navigatedTo) setLastNavigatedTitle(navigatedTo);

      const actions: { id: string; label: string }[] = [];
      if (updated) {
        actions.push({
          id: "view-updated",
          label: saved
            ? navigatedTo
              ? `已写入「${navigatedTo}」`
              : "已写入左侧知识库"
            : "查看更新内容",
        });
      } else if (reply.includes("待确认") || reply.includes("待补充")) {
        const markers = extractPendingMarkers(content);
        if (markers.length > 0) {
          actions.push({
            id: "open-pending-workspace",
            label: `去逐项补充（${markers.length}）`,
          });
        }
      }

      setMessages((prev) => [...prev, { role: "assistant", content: reply, actions }]);

      if (updated) {
        pushToast(
          saved ? "知识库已更新并已自动保存" : "知识库内容已更新，请确认后点击保存",
          saved ? "success" : "info"
        );
      } else if (/已(写入|更新|生成|整理|添加|补充)/.test(reply)) {
        pushToast(copy.knowledge.writeFailed, "warning");
      }
    } catch (e) {
      pushToast((e as Error).message, "error");
    } finally {
      setStreaming(false);
    }
  }

  async function handleChip(chip: string) {
    if (chip === copy.knowledge.chips.import) {
      if (!sessionId) {
        pushToast(copy.knowledge.importNeedResume, "warning");
        return;
      }
      setStreaming(true);
      try {
        const res = await api.knowledgeAgent.initFromResume({
          client_id: getClientId(),
          session_id: sessionId,
        });
        const md = res.data?.markdown;
        if (md) {
          onContentChange(md);
          onAutoSaved?.(md);
          pushToast(copy.knowledge.importOk, "success");
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: "已根据简历生成知识库草稿，含 [待确认] 标记的条目请逐项核对。" },
          ]);
        }
      } catch (e) {
        pushToast((e as Error).message, "error");
      } finally {
        setStreaming(false);
      }
      return;
    }

    if (chip === copy.knowledge.chips.star) {
      if (!selectedSection) {
        pushToast(copy.knowledge.selectTopic, "info");
        return;
      }
      setStreaming(true);
      try {
        const res = await api.knowledgeAgent.expandStar({
          section_title: selectedSection.title,
          content: selectedSection.content,
          hint: "",
        });
        const md = res.data?.markdown;
        if (md) {
          const updated = content.includes(selectedSection.content)
            ? content.replace(selectedSection.content, md.replace(/^##\s+[^\n]+\n?/, "").trim())
            : `${content}\n\n${md}`;
          onContentChange(updated);
          pushToast(copy.knowledge.starOk, "info");
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: `已补全「${selectedSection.title}」的 STAR 结构，请在中间栏确认。` },
          ]);
        }
      } catch (e) {
        pushToast((e as Error).message, "error");
      } finally {
        setStreaming(false);
      }
      return;
    }

    if (chip === copy.knowledge.chips.audit) {
      setStreaming(true);
      try {
        const res = await api.knowledgeAgent.audit({ content });
        const data = res.data;
        const markers = extractPendingMarkers(content);
        const summary =
          data?.summary ||
          `知识库中有 ${markers.length || data?.pending_count || 0} 处待补全/待确认。` +
            (data?.issues?.length ? `\n\n问题清单：\n${data.issues.map((x, i) => `${i + 1}. ${x}`).join("\n")}` : "");
        const actions: { id: string; label: string }[] = [];
        if (markers.length > 0) {
          actions.push({
            id: "open-pending-workspace",
            label: `去逐项补充（${markers.length}）`,
          });
        }
        if (data?.issues?.length) {
          actions.push({ id: "open-pending-workspace", label: "打开待确认工作台" });
        }
        setMessages((prev) => [...prev, { role: "assistant", content: summary, actions }]);
        if (markers.length > 0) {
          onOpenPendingWorkspace?.(markers[0]?.id ?? null);
        }
      } catch (e) {
        pushToast((e as Error).message, "error");
      } finally {
        setStreaming(false);
      }
      return;
    }

    if (chip === copy.knowledge.chips.merge) {
      onMergePending?.();
      return;
    }

    await sendMessage(chip);
  }

  return (
    <CopilotPanel
      mode="knowledge"
      contextLabel={contextLabel}
      messages={messages}
      quickChips={QUICK_CHIPS}
      streaming={streaming}
      onSend={sendMessage}
      onQuickChip={handleChip}
      onMessageAction={(id) => {
        if (id === "open-pending-workspace") onOpenPendingWorkspace?.();
        if (id === "view-updated") {
          const title = lastNavigatedTitle || selectedSection?.title;
          if (title) onSelectSectionByTitle?.(title);
        }
      }}
      placeholder={copy.knowledge.copilotPlaceholder}
    />
  );
}

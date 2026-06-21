"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { BookOpen, FileText, LayoutList, Loader2, Save } from "lucide-react";
import { api } from "@/lib/api";
import { getClientId, loadLocalMemory, saveLocalMemory } from "@/lib/userMemory";
import { useAppStore } from "@/stores/useAppStore";
import {
  countKnowledgeFacts,
  parseKnowledgeTopics,
  scrollToLine,
} from "@/lib/knowledgeTopics";
import {
  parseKnowledgeSections,
  sectionForLine,
  updateSectionContent,
} from "@/lib/knowledgeSections";
import KnowledgePendingWorkspace from "@/components/knowledge/KnowledgePendingWorkspace";
import KnowledgeSectionDetail from "@/components/knowledge/KnowledgeSectionDetail";
import KnowledgeCopilot from "@/components/copilot/KnowledgeCopilot";
import { getPersistedSessionId } from "@/lib/sessionBootstrap";
import { extractPendingMarkers } from "@/lib/knowledgePending";
import { copy } from "@/lib/copy";

type ViewMode = "structured" | "markdown";
type LeftTab = "topics" | "pending";

export default function AssetsPage() {
  const { sessionId: storeSessionId, setKnowledgeBase, pushToast } = useAppStore();
  const sessionId = storeSessionId || getPersistedSessionId();
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTopic, setActiveTopic] = useState<string | null>(null);
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("structured");
  const [leftTab, setLeftTab] = useState<LeftTab>("topics");
  const [focusPendingId, setFocusPendingId] = useState<string | null>(null);

  const loadKb = useCallback(async () => {
    setLoading(true);
    try {
      const local = loadLocalMemory();
      let kb = local.knowledge_base_md || "";

      const remote = await api.getUserMemory(getClientId()).catch(() => null);
      if (remote?.success && remote.data) {
        const r = remote.data as { knowledge_base_md?: string };
        if (r.knowledge_base_md) kb = r.knowledge_base_md;
      }

      if (!kb.trim()) {
        const tpl = await api.getKnowledgeTemplate();
        if (tpl.success && tpl.data?.template) kb = tpl.data.template;
      }

      if (sessionId) {
        const sess = await api.getKnowledgeBase(sessionId).catch(() => null);
        if (sess?.success && sess.data?.content?.trim()) {
          kb = sess.data.content;
        }
      }

      setContent(kb);
      setKnowledgeBase(kb);
    } finally {
      setLoading(false);
    }
  }, [sessionId, setKnowledgeBase]);

  useEffect(() => {
    loadKb();
  }, [loadKb]);

  const topics = useMemo(() => parseKnowledgeTopics(content), [content]);
  const sections = useMemo(() => parseKnowledgeSections(content), [content]);
  const factCount = useMemo(() => countKnowledgeFacts(content), [content]);
  const pendingCount = useMemo(() => extractPendingMarkers(content).length, [content]);
  const selectedSection = sections.find((s) => s.id === selectedSectionId) || null;

  useEffect(() => {
    if (viewMode !== "structured" || sections.length === 0) return;
    if (!selectedSectionId || !sections.some((s) => s.id === selectedSectionId)) {
      const first = sections[0];
      setSelectedSectionId(first.id);
      const topic = topics.find((t) => t.lineStart === first.lineStart);
      setActiveTopic(topic?.id ?? null);
    }
  }, [sections, selectedSectionId, viewMode, topics]);

  const pendingMarkers = useMemo(() => extractPendingMarkers(content), [content]);

  function openPendingWorkspace(focusId?: string | null) {
    setLeftTab("pending");
    setViewMode("structured");
    setFocusPendingId(focusId ?? null);
  }

  function selectTopic(topic: (typeof topics)[0]) {
    setActiveTopic(topic.id);
    if (topic.title.includes("待确认")) {
      openPendingWorkspace();
      return;
    }
    const sec = sectionForLine(sections, topic.lineStart);
    if (sec) setSelectedSectionId(sec.id);
    if (viewMode === "markdown") scrollToLine(topic.lineStart);
  }

  function updateSectionBody(section: (typeof sections)[0], body: string) {
    setContent((prev) => updateSectionContent(prev, section, body));
  }

  async function save() {
    setSaving(true);
    try {
      saveLocalMemory({ knowledge_base_md: content });
      await api.saveUserMemory({
        client_id: getClientId(),
        knowledge_base_md: content,
      });
      if (sessionId) {
        await api.saveKnowledgeBase(sessionId, content);
      }
      setKnowledgeBase(content);
      pushToast(copy.knowledge.savedToast, "success");
    } catch (e) {
      pushToast((e as Error).message, "error");
    } finally {
      setSaving(false);
    }
  }

  function selectSectionByTitle(title: string, md?: string) {
    const source = md ?? content;
    const secs = parseKnowledgeSections(source);
    const tops = parseKnowledgeTopics(source);
    const sec = secs.find(
      (s) => s.title === title || s.title.includes(title) || title.includes(s.title)
    );
    if (!sec) return;
    setSelectedSectionId(sec.id);
    setLeftTab("topics");
    setViewMode("structured");
    const topic = tops.find((t) => t.lineStart === sec.lineStart);
    if (topic) setActiveTopic(topic.id);
  }

  async function onKnowledgeAutoSaved(kb: string) {
    setContent(kb);
    setKnowledgeBase(kb);
    saveLocalMemory({ knowledge_base_md: kb });
    try {
      await api.saveUserMemory({
        client_id: getClientId(),
        knowledge_base_md: kb,
      });
      if (sessionId) {
        await api.saveKnowledgeBase(sessionId, kb);
      }
    } catch {
      /* toast already shown by copilot */
    }
  }

  function onMerged(kb: string) {
    setContent(kb);
    setKnowledgeBase(kb);
    saveLocalMemory({ knowledge_base_md: kb });
    pushToast(copy.knowledge.mergedToast, "info");
  }

  return (
    <div className="h-full flex flex-col min-h-[calc(100vh-var(--topbar-height,3.5rem))]">
      <div className="shrink-0 px-6 py-4 border-b border-[var(--border-subtle)] flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <BookOpen size={20} className="text-[var(--primary)]" />
            {copy.knowledge.title}
          </h1>
          <p className="page-subtitle">
            {copy.knowledge.subtitle(factCount, pendingCount)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-[var(--border-subtle)] overflow-hidden text-sm">
            <button
              type="button"
              onClick={() => setViewMode("structured")}
              className={`px-3 py-1.5 flex items-center gap-1 ${
                viewMode === "structured" ? "bg-[var(--primary)] text-white" : ""
              }`}
            >
              <LayoutList size={14} /> {copy.knowledge.structured}
            </button>
            <button
              type="button"
              onClick={() => setViewMode("markdown")}
              className={`px-3 py-1.5 flex items-center gap-1 ${
                viewMode === "markdown" ? "bg-[var(--primary)] text-white" : ""
              }`}
            >
              <FileText size={14} /> {copy.knowledge.raw}
            </button>
          </div>
          <button
            type="button"
            onClick={save}
            disabled={saving || loading}
            className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--primary)] text-white text-sm rounded-lg hover:opacity-90 disabled:opacity-50"
          >
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            {copy.knowledge.save}
          </button>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-12 min-h-0 overflow-hidden">
        {/* 左栏：主题 + 待确认 */}
        <aside className="col-span-2 xl:col-span-2 border-r border-[var(--border-subtle)] overflow-y-auto p-3 bg-[var(--surface-container)]">
          <div className="flex gap-1 mb-3 text-xs">
            <button
              type="button"
              onClick={() => setLeftTab("topics")}
              className={`flex-1 py-1 rounded ${leftTab === "topics" ? "bg-[var(--primary)]/10 text-[var(--primary)]" : "text-[var(--text-secondary)]"}`}
            >
              {copy.knowledge.topics}
            </button>
            <button
              type="button"
              onClick={() => {
                setLeftTab("pending");
                setFocusPendingId(null);
              }}
              className={`flex-1 py-1 rounded relative ${leftTab === "pending" ? "bg-[var(--primary)]/10 text-[var(--primary)]" : "text-[var(--text-secondary)]"}`}
            >
              {copy.knowledge.pending}
              {pendingMarkers.length > 0 && (
                <span className="ml-1 text-[10px] px-1 rounded-full bg-amber-100 text-amber-800">
                  {pendingMarkers.length}
                </span>
              )}
            </button>
          </div>
          {leftTab === "topics" ? (
            topics.length === 0 ? (
              <p className="text-xs text-[var(--text-disabled)]">{copy.knowledge.topicsEmpty}</p>
            ) : (
              <ul className="space-y-0.5">
                {topics.map((t) => (
                  <li key={t.id}>
                    <button
                      type="button"
                      onClick={() => selectTopic(t)}
                      className={`w-full text-left text-sm py-1.5 px-2 rounded transition-colors truncate ${
                        activeTopic === t.id
                          ? "bg-[var(--primary)]/10 text-[var(--primary)] font-medium"
                          : "text-[var(--text-secondary)] hover:bg-[var(--surface-base)]"
                      }`}
                      style={{ paddingLeft: `${(t.level - 1) * 10 + 8}px` }}
                    >
                      {t.title}
                    </button>
                  </li>
                ))}
              </ul>
            )
          ) : (
            <p className="text-xs text-[var(--text-disabled)] leading-relaxed">
              {copy.knowledge.pendingHint}
            </p>
          )}
        </aside>

        {/* 中栏：结构化详情 / Markdown 编辑 */}
        <main className="col-span-7 xl:col-span-8 overflow-y-auto p-4 md:p-6 bg-[var(--surface-base)] min-h-0">
          {loading ? (
            <div className="flex items-center justify-center h-40 text-[var(--text-disabled)]">
              <Loader2 size={24} className="animate-spin" />
            </div>
          ) : viewMode === "markdown" ? (
            <textarea
              id="knowledge-editor"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="w-full h-full min-h-[60vh] p-4 text-sm font-mono leading-relaxed resize-none rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-container)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
              placeholder={copy.knowledge.editorPlaceholder}
              spellCheck={false}
            />
          ) : leftTab === "pending" ? (
            <KnowledgePendingWorkspace
              content={content}
              onContentChange={setContent}
              onMerged={onMerged}
              focusItemId={focusPendingId}
            />
          ) : sections.length === 0 ? (
            <p className="text-sm text-[var(--text-disabled)]">
              {copy.knowledge.sectionsEmpty}
            </p>
          ) : selectedSection?.title.includes("待确认") ? (
            <KnowledgePendingWorkspace
              content={content}
              onContentChange={setContent}
              onMerged={onMerged}
              focusItemId={focusPendingId}
            />
          ) : selectedSection ? (
            <KnowledgeSectionDetail
              key={selectedSection.id}
              section={selectedSection}
              sessionId={sessionId || undefined}
              focusLine={
                activeTopic
                  ? topics.find((t) => t.id === activeTopic)?.lineStart ?? null
                  : null
              }
              onContentChange={(body) => updateSectionBody(selectedSection, body)}
              onOpenPendingWorkspace={() => openPendingWorkspace()}
              pendingInSection={extractPendingMarkers(selectedSection.content).length}
            />
          ) : null}
        </main>

        {/* 右栏 Copilot */}
        <div className="col-span-3 xl:col-span-2 min-h-0 overflow-hidden border-l border-[var(--border-subtle)]">
          <KnowledgeCopilot
            content={content}
            onContentChange={setContent}
            selectedSection={selectedSection}
            viewMode={viewMode}
            leftTab={leftTab}
            onAutoSaved={onKnowledgeAutoSaved}
            onSelectSectionByTitle={selectSectionByTitle}
            onMergePending={async () => {
              try {
                const res = await api.mergePendingToKnowledge(getClientId());
                if (res.success && res.data?.knowledge_base_md) {
                  onMerged(res.data.knowledge_base_md);
                }
              } catch (e) {
                pushToast((e as Error).message, "error");
              }
            }}
            onOpenPendingWorkspace={openPendingWorkspace}
          />
        </div>
      </div>
    </div>
  );
}

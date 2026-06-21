"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Pencil, Eye, ArrowRight } from "lucide-react";
import type { KnowledgeSection } from "@/lib/knowledgeSections";
import { countPendingMarkers, isPhotoSection } from "@/lib/knowledgeSections";
import KnowledgeStructuredView from "@/components/knowledge/KnowledgeStructuredView";
import ProfilePhotoModule from "@/components/upload/ProfilePhotoModule";
import { ROUTES } from "@/lib/navigation";

type Props = {
  section: KnowledgeSection;
  sessionId?: string;
  focusLine?: number | null;
  onContentChange: (body: string) => void;
  onOpenPendingWorkspace?: () => void;
  pendingInSection?: number;
};

export default function KnowledgeSectionDetail({
  section,
  sessionId,
  focusLine,
  onContentChange,
  onOpenPendingWorkspace,
  pendingInSection = 0,
}: Props) {
  const [mode, setMode] = useState<"preview" | "edit">("preview");
  const [draft, setDraft] = useState(section.content);
  const pending = countPendingMarkers(section.content);
  const showPhoto = isPhotoSection(section) || /###\s+个人照片/.test(section.content);

  const displayContent = useMemo(() => {
    if (!showPhoto) return section.content;
    return section.content
      .replace(/###\s+个人照片[\s\S]*?(?=\n###\s+|$)/, "")
      .trim();
  }, [section.content, showPhoto]);

  useEffect(() => {
    setDraft(section.content);
    setMode("preview");
  }, [section.id, section.content]);

  const subTopics = useMemo(() => {
    return section.content
      .split("\n")
      .map((line, i) => {
        const m = /^###\s+(.+)/.exec(line);
        return m ? { title: m[1].trim(), offset: i } : null;
      })
      .filter(Boolean) as { title: string; offset: number }[];
  }, [section.content]);

  function saveDraft() {
    onContentChange(draft);
    setMode("preview");
  }

  return (
    <article className="h-full flex flex-col min-h-0">
      <header className="shrink-0 mb-4 pb-3 border-b border-[var(--border-subtle)]">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">{section.title}</h2>
            {pending > 0 && (
              <p className="text-xs text-[var(--semantic-warning)] mt-1">{pending} 处待确认</p>
            )}
          </div>
          <div className="flex rounded-lg border border-[var(--border-subtle)] overflow-hidden text-xs">
            <button
              type="button"
              onClick={() => setMode("preview")}
              className={`px-3 py-1.5 flex items-center gap-1 ${
                mode === "preview" ? "bg-[var(--primary)] text-white" : ""
              }`}
            >
              <Eye size={13} /> 预览
            </button>
            <button
              type="button"
              onClick={() => setMode("edit")}
              className={`px-3 py-1.5 flex items-center gap-1 ${
                mode === "edit" ? "bg-[var(--primary)] text-white" : ""
              }`}
            >
              <Pencil size={13} /> 编辑
            </button>
          </div>
        </div>
        {subTopics.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3">
            {subTopics.map((t) => (
              <span
                key={t.title}
                className="text-xs px-2 py-0.5 rounded-full bg-[var(--surface-container)] border border-[var(--border-subtle)] text-[var(--text-secondary)]"
              >
                {t.title}
              </span>
            ))}
          </div>
        )}
      </header>

      <div className="flex-1 min-h-0 overflow-y-auto space-y-4">
        {pendingInSection > 0 && onOpenPendingWorkspace && (
          <div className="p-3 rounded-xl border border-amber-200 bg-amber-50 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-amber-900">
              本节有 {pendingInSection} 处待补全，可在工作台逐项填写并写入知识库。
            </p>
            <button
              type="button"
              onClick={onOpenPendingWorkspace}
              className="inline-flex items-center gap-1 text-sm text-[var(--primary)] font-medium hover:underline"
            >
              去补充 <ArrowRight size={14} />
            </button>
          </div>
        )}
        {showPhoto && (
          <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-container)] p-1">
            {sessionId ? (
              <ProfilePhotoModule sessionId={sessionId} />
            ) : (
              <div className="p-4 text-sm text-[var(--text-secondary)]">
                <p className="mb-2">上传照片需先开始一次改稿会话（用于关联简历与导出）。</p>
                <Link href={ROUTES.studioPrepare} className="text-[var(--primary)] hover:underline">
                  去新建改稿 →
                </Link>
              </div>
            )}
          </div>
        )}

        {mode === "edit" ? (
          <div className="space-y-3">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className="w-full min-h-[50vh] p-4 text-sm font-mono leading-relaxed rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-container)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
              spellCheck={false}
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={saveDraft}
                className="px-4 py-2 bg-[var(--primary)] text-white text-sm rounded-lg"
              >
                应用修改
              </button>
              <button
                type="button"
                onClick={() => {
                  setDraft(section.content);
                  setMode("preview");
                }}
                className="px-4 py-2 border border-[var(--border-subtle)] text-sm rounded-lg"
              >
                取消
              </button>
            </div>
          </div>
        ) : (
          <div
            className="p-5 rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-container)]"
            data-focus-line={focusLine ?? undefined}
          >
            <KnowledgeStructuredView content={displayContent} />
          </div>
        )}
      </div>
    </article>
  );
}

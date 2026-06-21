"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import type { PendingKnowledgeItem } from "@/lib/types";
import {
  extractPendingMarkers,
  removePendingMarker,
  resolvePendingMarker,
  type PendingMarkerItem,
} from "@/lib/knowledgePending";
import { Check, Loader2, SkipForward, Sparkles, X } from "lucide-react";
import { copy } from "@/lib/copy";

type Props = {
  content: string;
  onContentChange: (md: string) => void;
  onMerged?: (kb: string) => void;
  focusItemId?: string | null;
};

export default function KnowledgePendingWorkspace({
  content,
  onContentChange,
  onMerged,
  focusItemId,
}: Props) {
  const [sinkItems, setSinkItems] = useState<PendingKnowledgeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [merging, setMerging] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const markers = useMemo(() => extractPendingMarkers(content), [content]);

  const loadSink = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getPendingKnowledge(getClientId());
      if (res.success && res.data) setSinkItems(res.data.items || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSink();
  }, [loadSink]);

  useEffect(() => {
    if (!focusItemId) return;
    const el = document.getElementById(`pending-item-${focusItemId}`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusItemId, markers.length]);

  async function resolveSink(id: string, action: "confirm" | "ignore") {
    await api.confirmPendingKnowledge(getClientId(), id, action);
    await loadSink();
  }

  async function mergeSink() {
    setMerging(true);
    try {
      const res = await api.mergePendingToKnowledge(getClientId());
      if (res.success && res.data?.knowledge_base_md) {
        onMerged?.(res.data.knowledge_base_md);
        await loadSink();
      }
    } finally {
      setMerging(false);
    }
  }

  function applyMarker(item: PendingMarkerItem) {
    const value = drafts[item.id]?.trim();
    if (!value) return;
    onContentChange(resolvePendingMarker(content, item, value));
    setDrafts((d) => {
      const next = { ...d };
      delete next[item.id];
      return next;
    });
  }

  function skipMarker(item: PendingMarkerItem) {
    onContentChange(removePendingMarker(content, item));
  }

  const sinkPending = sinkItems.filter((i) => i.status === "pending");
  const total = markers.length + sinkPending.length;

  if (loading && total === 0) {
    return (
      <div className="flex justify-center py-16 text-[var(--text-disabled)]">
        <Loader2 size={22} className="animate-spin" />
      </div>
    );
  }

  if (total === 0) {
    return (
      <div className="py-12 text-center text-sm text-[var(--text-secondary)]">
        <Sparkles size={28} className="mx-auto mb-3 text-[var(--primary)] opacity-60" />
        <p>暂无待确认项。改稿产生的新事实会出现在「改稿沉淀」区。</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">待确认工作台</h2>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          共 {total} 项：填写补充内容后点「确认写入」，或直接忽略。
        </p>
      </div>

      {markers.length > 0 && (
        <section className="space-y-3">
          <h3 className="text-sm font-medium text-[var(--text-primary)]">
            知识库内待补全（{markers.length}）
          </h3>
          {markers.map((item) => (
            <article
              key={item.id}
              id={`pending-item-${item.id}`}
              className="p-4 rounded-xl border border-amber-200 bg-amber-50/50 space-y-3"
            >
              <div className="text-xs font-medium text-amber-800">
                {item.kind === "待补充" ? `需补充：${item.label}` : "待确认事实"}
              </div>
              <p className="text-sm text-[var(--text-primary)] leading-relaxed">{item.context}</p>
              <div className="flex flex-wrap gap-2 items-center">
                <input
                  className="flex-1 min-w-[200px] text-sm px-3 py-2 rounded-lg border border-[var(--border-subtle)] bg-white"
                  placeholder={
                    item.kind === "待补充"
                      ? `填写${item.label}，如：120 条、提升 15%`
                      : "填写确认后的事实描述"
                  }
                  value={drafts[item.id] || ""}
                  onChange={(e) => setDrafts((d) => ({ ...d, [item.id]: e.target.value }))}
                  onKeyDown={(e) => e.key === "Enter" && applyMarker(item)}
                />
                <button
                  type="button"
                  disabled={!drafts[item.id]?.trim()}
                  onClick={() => applyMarker(item)}
                  className="inline-flex items-center gap-1 px-3 py-2 text-sm bg-[var(--primary)] text-white rounded-lg disabled:opacity-40"
                >
                  <Check size={14} /> 确认写入
                </button>
                <button
                  type="button"
                  onClick={() => skipMarker(item)}
                  className="inline-flex items-center gap-1 px-3 py-2 text-sm border border-[var(--border-subtle)] rounded-lg bg-white text-[var(--text-secondary)]"
                >
                  <SkipForward size={14} /> 移除标记
                </button>
              </div>
            </article>
          ))}
        </section>
      )}

      {sinkPending.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-medium text-[var(--text-primary)]">
              改稿沉淀待确认（{sinkPending.length}）
            </h3>
            <button
              type="button"
              onClick={mergeSink}
              disabled={merging || !sinkItems.some((i) => i.status === "confirmed")}
              className="text-xs text-[var(--primary)] hover:underline disabled:text-[var(--text-disabled)]"
            >
              {merging ? "合并中…" : "合并已确认到知识库"}
            </button>
          </div>
          {sinkPending.map((item) => (
            <article
              key={item.id}
              id={`pending-item-sink-${item.id}`}
              className="p-4 rounded-xl border border-[var(--primary)]/20 bg-[var(--primary-muted)]/40 space-y-2"
            >
              <div className="text-xs text-[var(--primary)]">来源：{item.source || copy.knowledge.sourceEdit}</div>
              {item.original_text && (
                <p className="text-xs text-[var(--text-disabled)] line-through">
                  原：{item.original_text.slice(0, 120)}
                </p>
              )}
              <p className="text-sm text-[var(--text-primary)]">{item.new_text}</p>
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => resolveSink(item.id, "confirm")}
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100"
                >
                  <Check size={14} /> 确认沉淀
                </button>
                <button
                  type="button"
                  onClick={() => resolveSink(item.id, "ignore")}
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-sm text-[var(--text-secondary)] bg-white border border-[var(--border-subtle)] rounded-lg"
                >
                  <X size={14} /> 忽略
                </button>
              </div>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}

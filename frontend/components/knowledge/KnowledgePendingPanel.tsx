"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import type { PendingKnowledgeItem } from "@/lib/types";
import { BookMarked, Check, Loader2, X } from "lucide-react";

type Props = {
  onMerged?: (kb: string) => void;
};

export default function KnowledgePendingPanel({ onMerged }: Props) {
  const [items, setItems] = useState<PendingKnowledgeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [merging, setMerging] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getPendingKnowledge(getClientId());
      if (res.success && res.data) setItems(res.data.items || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function resolve(id: string, action: "confirm" | "ignore") {
    await api.confirmPendingKnowledge(getClientId(), id, action);
    await load();
  }

  async function mergeAll() {
    setMerging(true);
    try {
      const res = await api.mergePendingToKnowledge(getClientId());
      if (res.success && res.data?.knowledge_base_md) {
        onMerged?.(res.data.knowledge_base_md);
        await load();
      }
    } finally {
      setMerging(false);
    }
  }

  const pending = items.filter((i) => i.status === "pending");

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-[var(--text-primary)] flex items-center gap-2 text-sm">
          <BookMarked size={16} className="text-purple-600" />
          待沉淀 ({pending.length})
        </h3>
        <button
          type="button"
          onClick={mergeAll}
          disabled={merging || !items.some((i) => i.status === "confirmed")}
          className="text-xs text-[var(--primary)] hover:underline disabled:text-[var(--text-disabled)]"
        >
          {merging ? "合并中…" : "合并已确认"}
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-8 text-[var(--text-disabled)]">
          <Loader2 size={20} className="animate-spin" />
        </div>
      ) : pending.length === 0 ? (
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          接受简历修改建议后，新内容会出现在这里。确认后合并进知识库。
        </p>
      ) : (
        <ul className="space-y-2 flex-1 overflow-y-auto pr-1">
          {pending.map((item) => (
            <li
              key={item.id}
              className="p-2 bg-purple-50 border border-purple-100 rounded-lg text-xs"
            >
              <div className="text-[var(--text-secondary)] mb-1">{item.source || "edit"}</div>
              <p className="text-[var(--text-primary)] line-clamp-3">{item.new_text}</p>
              <div className="flex gap-1 mt-2 justify-end">
                <button
                  type="button"
                  onClick={() => resolve(item.id, "confirm")}
                  className="inline-flex items-center gap-1 px-2 py-1 text-green-700 bg-green-50 rounded hover:bg-green-100"
                >
                  <Check size={12} /> 确认
                </button>
                <button
                  type="button"
                  onClick={() => resolve(item.id, "ignore")}
                  className="inline-flex items-center gap-1 px-2 py-1 text-[var(--text-secondary)] bg-[var(--surface-base)] rounded hover:bg-[var(--border-subtle)]"
                >
                  <X size={12} /> 忽略
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import type { PendingKnowledgeItem } from "@/lib/types";
import { BookMarked, Check, X } from "lucide-react";

export default function PendingKnowledgePanel() {
  const [items, setItems] = useState<PendingKnowledgeItem[]>([]);
  const [loading, setLoading] = useState(false);

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
    const res = await api.mergePendingToKnowledge(getClientId());
    if (res.success) {
      await load();
    }
  }

  if (!items.length && !loading) return null;

  return (
    <div className="mx-6 mb-2 p-3 bg-purple-50 border border-purple-200 rounded-lg text-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="font-medium text-purple-900 flex items-center gap-1">
          <BookMarked size={14} /> 候选事实待归档 ({items.length})
        </span>
        <button
          type="button"
          onClick={mergeAll}
          className="text-xs text-purple-700 hover:underline"
        >
          写入已确认字段
        </button>
      </div>
      <ul className="space-y-2 max-h-32 overflow-y-auto">
        {items.map((item) => (
          <li key={item.id} className="flex gap-2 items-start bg-white/80 p-2 rounded border border-purple-100">
            <div className="flex-1 text-xs text-[var(--text-secondary)] line-clamp-2">
              {(item.facts || []).map((f) => `${f.field}：${f.value}`).join("；") || item.new_text}
            </div>
            <button
              type="button"
              disabled
              className="p-1 text-green-600 rounded opacity-40"
              title="请到知识库待核对工作台选择归属经历后确认"
            >
              <Check size={14} />
            </button>
            <button
              type="button"
              onClick={() => resolve(item.id, "ignore")}
              className="p-1 text-[var(--text-disabled)] hover:bg-[var(--surface-base)] rounded"
              title="忽略"
            >
              <X size={14} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

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
          <BookMarked size={14} /> 待沉淀到知识库 ({items.length})
        </span>
        <button
          type="button"
          onClick={mergeAll}
          className="text-xs text-purple-700 hover:underline"
        >
          合并已确认到知识库
        </button>
      </div>
      <ul className="space-y-2 max-h-32 overflow-y-auto">
        {items.map((item) => (
          <li key={item.id} className="flex gap-2 items-start bg-white/80 p-2 rounded border border-purple-100">
            <div className="flex-1 text-xs text-slate-700 line-clamp-2">{item.new_text}</div>
            <button
              type="button"
              onClick={() => resolve(item.id, "confirm")}
              className="p-1 text-green-600 hover:bg-green-50 rounded"
              title="确认沉淀"
            >
              <Check size={14} />
            </button>
            <button
              type="button"
              onClick={() => resolve(item.id, "ignore")}
              className="p-1 text-slate-400 hover:bg-slate-100 rounded"
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

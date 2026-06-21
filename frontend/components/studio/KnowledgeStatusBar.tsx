"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BookOpen, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import { countKnowledgeFacts } from "@/lib/knowledgeTopics";
import { getClientId } from "@/lib/userMemory";
import { ROUTES } from "@/lib/navigation";

export default function KnowledgeStatusBar() {
  const [facts, setFacts] = useState(0);
  const [pending, setPending] = useState(0);

  useEffect(() => {
    api.getUserMemory(getClientId()).then((res) => {
      const kb = (res.data as { knowledge_base_md?: string })?.knowledge_base_md || "";
      setFacts(countKnowledgeFacts(kb));
    }).catch(() => {});
    api.getPendingKnowledge(getClientId()).then((res) => {
      const items = res.data?.items || [];
      setPending(items.filter((i) => i.status === "pending").length);
    }).catch(() => {});
  }, []);

  const completeness = facts === 0 ? 0 : Math.min(100, Math.round((facts / 20) * 100));

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-container)] text-sm">
      <div className="flex items-center gap-2 text-[var(--text-secondary)]">
        <BookOpen size={16} className="text-[var(--primary)]" />
        <span>
          知识库约 {completeness}% 完整 · {facts} 条事实
          {pending > 0 && (
            <span className="text-[var(--semantic-warning)]"> · {pending} 条待确认</span>
          )}
        </span>
      </div>
      <Link
        href={ROUTES.assets}
        className="inline-flex items-center gap-1 text-[var(--primary)] hover:underline font-medium"
      >
        去完善 <ChevronRight size={14} />
      </Link>
    </div>
  );
}

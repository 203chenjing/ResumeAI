"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { countKnowledgeFacts } from "@/lib/knowledgeTopics";
import { getClientId, loadLocalMemory } from "@/lib/userMemory";
import type { ApplicationStats } from "@/lib/types";

export default function GlanceStats() {
  const [facts, setFacts] = useState(0);
  const [stats, setStats] = useState<ApplicationStats | null>(null);

  useEffect(() => {
    const local = loadLocalMemory();
    api.getUserMemory(getClientId()).then((res) => {
      const kb = (res.data as { knowledge_base_md?: string })?.knowledge_base_md || local.knowledge_base_md || "";
      setFacts(countKnowledgeFacts(kb));
    }).catch(() => {});
    api.getApplications(getClientId()).then((res) => {
      if (res.success && res.data) setStats(res.data.stats);
    }).catch(() => {});
  }, []);

  const completeness = facts === 0 ? 0 : Math.min(100, Math.round((facts / 20) * 100));

  return (
    <div className="grid grid-cols-3 gap-3">
      <Stat label="知识库完整度" value={`${completeness}%`} />
      <Stat label="投递记录" value={String(stats?.applied_count ?? stats?.total ?? 0)} />
      <Stat label="面试/Offer" value={`${stats?.interview_count ?? 0}/${stats?.offer_count ?? 0}`} />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-container)] text-center">
      <div className="text-lg font-semibold">{value}</div>
      <div className="text-xs text-[var(--text-secondary)] mt-1">{label}</div>
    </div>
  );
}

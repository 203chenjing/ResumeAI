"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Archive, Briefcase, BookOpen, ChevronRight } from "lucide-react";
import ContinueCard from "@/components/hub/ContinueCard";
import TodayBriefingCard from "@/components/hub/TodayBriefingCard";
import TodoList from "@/components/hub/TodoList";
import GlanceStats from "@/components/hub/GlanceStats";
import { EMPTY_STUDIO_META, getLastStudioMeta, persistSessionId } from "@/lib/sessionBootstrap";
import { ROUTES } from "@/lib/navigation";
import { copy } from "@/lib/copy";
import { api } from "@/lib/api";
import type { SessionArchive } from "@/lib/types";

const SHORTCUTS = [
  { href: ROUTES.jobs, label: copy.hub.discoverJobs, icon: Briefcase },
  { href: ROUTES.assets, label: copy.hub.organizeKb, icon: BookOpen },
] as const;

export default function HubPage() {
  const [meta, setMeta] = useState(EMPTY_STUDIO_META);
  const [archives, setArchives] = useState<SessionArchive[]>([]);

  useEffect(() => {
    setMeta(getLastStudioMeta());
    api.getRecentSessions(6).then((res) => {
      if (res.success && res.data) setArchives(res.data.sessions);
    }).catch(() => {});
  }, []);

  function archiveHref(item: SessionArchive) {
    if (item.finalize_status === "finalized") return ROUTES.studioExport;
    if (item.suggestions_total > 0 || item.status === "suggestions_ready") return ROUTES.studioEdit;
    return ROUTES.studioPrepare;
  }

  function continueArchive(item: SessionArchive) {
    persistSessionId(item.session_id);
    window.location.assign(archiveHref(item));
  }

  return (
    <div className="page-shell space-y-8">
      <header>
        <h1 className="page-title">{copy.nav.hub}</h1>
        <p className="page-subtitle">{copy.hub.subtitle}</p>
      </header>

      <ContinueCard meta={meta} />

      {archives.length > 0 && (
        <section className="surface-card p-4">
          <div className="flex items-center justify-between gap-3 mb-3">
            <div>
              <p className="section-label mb-1">最近存档</p>
              <h2 className="text-base font-medium text-[var(--text-primary)]">已自动保存的简历工作区</h2>
            </div>
            <Archive size={18} className="text-[var(--text-secondary)]" />
          </div>
          <div className="grid md:grid-cols-2 gap-3">
            {archives.map((item) => (
              <button
                key={item.session_id}
                type="button"
                onClick={() => continueArchive(item)}
                className="text-left rounded-[var(--radius-md)] border border-[var(--border-subtle)] p-3 hover:border-[var(--primary)] hover:bg-[var(--primary-muted)]/40 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium text-[var(--text-primary)] truncate">{item.title}</p>
                    <p className="text-xs text-[var(--text-secondary)] mt-1">
                      {item.finalize_status === "finalized"
                        ? "已定稿"
                        : item.pending_suggestions > 0
                          ? `${item.pending_suggestions} 条建议待处理`
                          : "自动保存"}
                    </p>
                  </div>
                  <ChevronRight size={16} className="text-[var(--text-disabled)] mt-1 shrink-0" />
                </div>
                <p className="text-[11px] text-[var(--text-disabled)] mt-2">
                  更新于 {formatArchiveTime(item.updated_at)}
                </p>
              </button>
            ))}
          </div>
        </section>
      )}

      <TodayBriefingCard />

      <div className="grid md:grid-cols-5 gap-4">
        <div className="md:col-span-3">
          <TodoList />
        </div>
        <div className="md:col-span-2 surface-card p-4">
          <p className="section-label mb-3">{copy.hub.shortcuts}</p>
          <div className="flex flex-col">
            {SHORTCUTS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className="flex items-center justify-between py-2.5 px-1 text-sm text-[var(--text-primary)] hover:text-[var(--primary)] transition-colors group"
              >
                <span className="flex items-center gap-2.5">
                  <Icon size={18} className="text-[var(--text-secondary)] group-hover:text-[var(--primary)]" />
                  {label}
                </span>
                <ChevronRight size={16} className="text-[var(--text-disabled)] group-hover:text-[var(--primary)]" />
              </Link>
            ))}
          </div>
        </div>
      </div>

      <GlanceStats />
    </div>
  );
}

function formatArchiveTime(iso?: string) {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso.slice(0, 16);
  const mins = Math.floor((Date.now() - t) / 60000);
  if (mins < 60) return `${Math.max(1, mins)} 分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 48) return `${hours} 小时前`;
  return iso.slice(0, 10);
}

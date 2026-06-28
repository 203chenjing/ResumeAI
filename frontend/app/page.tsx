"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Briefcase, BookOpen, ChevronRight } from "lucide-react";
import ContinueCard from "@/components/hub/ContinueCard";
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
    <div className="page-shell space-y-6">
      <header>
        <h1 className="page-title">{copy.nav.hub}</h1>
        <p className="page-subtitle">{copy.hub.subtitle}</p>
      </header>

      <ContinueCard meta={meta} archives={archives} onSelectArchive={continueArchive} />

      <div className="flex flex-wrap gap-2">
        {SHORTCUTS.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-[var(--radius-full)] text-sm border border-[var(--border-subtle)] bg-[var(--surface-container)] text-[var(--text-primary)] hover:border-[var(--primary)] hover:text-[var(--primary)] transition-colors"
          >
            <Icon size={16} className="text-[var(--text-secondary)]" />
            {label}
          </Link>
        ))}
      </div>

      <TodoList />

      <GlanceStats />
    </div>
  );
}

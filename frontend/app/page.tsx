"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Briefcase, BookOpen, ChevronRight } from "lucide-react";
import ContinueCard from "@/components/hub/ContinueCard";
import TodoList from "@/components/hub/TodoList";
import GlanceStats from "@/components/hub/GlanceStats";
import { EMPTY_STUDIO_META, getLastStudioMeta } from "@/lib/sessionBootstrap";
import { ROUTES } from "@/lib/navigation";
import { copy } from "@/lib/copy";

const SHORTCUTS = [
  { href: ROUTES.jobs, label: copy.hub.discoverJobs, icon: Briefcase },
  { href: ROUTES.assets, label: copy.hub.organizeKb, icon: BookOpen },
] as const;

export default function HubPage() {
  const [meta, setMeta] = useState(EMPTY_STUDIO_META);

  useEffect(() => {
    setMeta(getLastStudioMeta());
  }, []);

  return (
    <div className="page-shell space-y-8">
      <header>
        <h1 className="page-title">{copy.nav.hub}</h1>
        <p className="page-subtitle">{copy.hub.subtitle}</p>
      </header>

      <ContinueCard meta={meta} />

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

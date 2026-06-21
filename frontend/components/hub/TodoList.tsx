"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ChevronRight, Circle } from "lucide-react";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import { ROUTES } from "@/lib/navigation";
import type { Reminder } from "@/lib/types";
import { copy } from "@/lib/copy";

export default function TodoList() {
  const [pendingKb, setPendingKb] = useState(0);
  const [reminders, setReminders] = useState<Reminder[]>([]);

  useEffect(() => {
    api.getPendingKnowledge(getClientId()).then((res) => {
      const items = res.data?.items || [];
      setPendingKb(items.filter((i) => i.status === "pending").length);
    }).catch(() => {});
    api.getReminders(getClientId()).then((res) => {
      if (res.success && res.data) setReminders((res.data.reminders || []).slice(0, 5));
    }).catch(() => {});
  }, []);

  const todos: { label: string; href: string }[] = [];
  if (pendingKb > 0) {
    todos.push({ label: copy.hub.kbPendingShort(pendingKb), href: ROUTES.assets });
  }
  for (const r of reminders) {
    todos.push({ label: r.message, href: ROUTES.tracker });
  }

  if (!todos.length) {
    return (
      <div className="surface-card p-5">
        <p className="section-label mb-1">{copy.hub.todosTitle}</p>
        <p className="text-sm text-[var(--text-secondary)]">{copy.hub.noTodos}</p>
      </div>
    );
  }

  return (
    <div className="surface-card p-5">
      <p className="section-label mb-3">{copy.hub.todosTitle}</p>
      <ul className="divide-y divide-[var(--border-faint)]">
        {todos.map((t, i) => (
          <li key={i}>
            <Link
              href={t.href}
              className="flex items-center justify-between py-3 text-sm text-[var(--text-primary)] hover:text-[var(--primary)] transition-colors group"
            >
              <span className="flex items-center gap-2.5 min-w-0">
                <Circle size={8} className="shrink-0 fill-[var(--primary)] text-[var(--primary)]" />
                <span className="truncate">{t.label}</span>
              </span>
              <ChevronRight size={16} className="shrink-0 text-[var(--text-disabled)] group-hover:text-[var(--primary)]" />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

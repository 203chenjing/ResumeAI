"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import { ROUTES } from "@/lib/navigation";
import type { Reminder } from "@/lib/types";

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
    todos.push({ label: `知识库 ${pendingKb} 条待确认`, href: ROUTES.assets });
  }
  for (const r of reminders) {
    todos.push({ label: r.message, href: ROUTES.tracker });
  }

  if (!todos.length) {
    return (
      <div className="p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-container)] text-sm text-[var(--text-secondary)]">
        暂无待办
      </div>
    );
  }

  return (
    <div className="p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-container)]">
      <h3 className="text-sm font-semibold mb-3">待办</h3>
      <ul className="space-y-2">
        {todos.map((t, i) => (
          <li key={i}>
            <Link href={t.href} className="text-sm text-[var(--primary)] hover:underline">
              ○ {t.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

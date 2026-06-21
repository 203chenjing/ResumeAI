"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { ROUTES } from "@/lib/navigation";
import { getLastStudioMeta } from "@/lib/sessionBootstrap";
import { useAppStore } from "@/stores/useAppStore";

interface Command {
  id: string;
  label: string;
  href?: string;
  action?: () => void;
  keywords?: string;
}

export default function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const router = useRouter();
  const finalizeStatus = useAppStore((s) => s.finalizeStatus);
  const [q, setQ] = useState("");

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onOpenChange(!open);
      }
      if (e.key === "Escape") onOpenChange(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  const commands = useMemo<Command[]>(() => {
    const last = getLastStudioMeta();
    const base: Command[] = [
      {
        id: "continue",
        label: last.sessionId ? `继续改稿 · ${last.company || last.role || "上次会话"}` : "继续改稿",
        href: last.step === 3 ? ROUTES.studioExport : last.step === 1 ? ROUTES.studioPrepare : ROUTES.studioEdit,
        keywords: "继续 resume edit",
      },
      { id: "new", label: "新建改稿", href: ROUTES.studioPrepare, keywords: "新建 upload" },
      { id: "assets", label: "整理知识库", href: ROUTES.assets, keywords: "knowledge 知识库" },
      { id: "jobs", label: "发现岗位", href: ROUTES.jobs, keywords: "岗位 job" },
      { id: "tracker", label: "投递看板", href: ROUTES.tracker, keywords: "投递 tracker" },
    ];
    if (finalizeStatus === "finalized") {
      base.push({ id: "export", label: "导出 PDF", href: ROUTES.studioExport, keywords: "pdf export" });
    }
    return base;
  }, [finalizeStatus]);

  const filtered = useMemo(() => {
    const qLower = q.trim().toLowerCase();
    const list = commands.filter(
      (c) =>
        !qLower ||
        c.label.toLowerCase().includes(qLower) ||
        (c.keywords || "").toLowerCase().includes(qLower)
    );
    if (q.trim() && !list.some((c) => c.id === "search-jobs")) {
      list.push({
        id: "search-jobs",
        label: `搜索岗位「${q.trim()}」`,
        href: `${ROUTES.jobs}?filter=${encodeURIComponent(q.trim())}`,
        keywords: "search job filter",
      });
    }
    return list;
  }, [commands, q]);

  if (!open) return null;

  function run(cmd: Command) {
    onOpenChange(false);
    setQ("");
    if (cmd.action) cmd.action();
    else if (cmd.href) router.push(cmd.href);
  }

  return (
    <div
      className="fixed inset-0 z-[200] flex items-start justify-center pt-[15vh] bg-black/40 px-4"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="w-full max-w-lg bg-[var(--surface-container)] rounded-xl shadow-2xl border border-[var(--border-subtle)] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border-subtle)]">
          <Search size={16} className="text-[var(--text-disabled)]" />
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜索命令…"
            className="flex-1 bg-transparent text-sm outline-none text-[var(--text-primary)]"
          />
        </div>
        <ul className="max-h-72 overflow-y-auto py-2">
          {filtered.map((cmd) => (
            <li key={cmd.id}>
              <button
                type="button"
                onClick={() => run(cmd)}
                className="w-full text-left px-4 py-2.5 text-sm hover:bg-[var(--surface-base)] text-[var(--text-primary)]"
              >
                {cmd.label}
              </button>
            </li>
          ))}
          {filtered.length === 0 && (
            <li className="px-4 py-6 text-sm text-[var(--text-disabled)] text-center">无匹配命令</li>
          )}
        </ul>
      </div>
    </div>
  );
}

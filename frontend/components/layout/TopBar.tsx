"use client";

import Link from "next/link";
import { Search, Sparkles } from "lucide-react";
import { useAppStore } from "@/stores/useAppStore";
import { buildStudioContext } from "@/lib/navigation";
import { CrawlStatusChip } from "./CrawlStatusIndicator";

export default function TopBar({ onOpenCommand }: { onOpenCommand?: () => void }) {
  const jdAnalysis = useAppStore((s) => s.jdAnalysis);
  const ctx = buildStudioContext(jdAnalysis);

  return (
    <header className="h-14 border-b border-[var(--border-subtle)] bg-[var(--surface-container)] flex items-center justify-between px-4 shrink-0">
      <Link href="/" className="flex items-center gap-2 text-[var(--primary)] font-semibold">
        <Sparkles size={18} />
        <span className="hidden sm:inline">ResumeAI</span>
      </Link>

      {ctx && (
        <div className="hidden md:flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <span className="px-2 py-0.5 rounded-full bg-[var(--surface-base)] border border-[var(--border-subtle)]">
            {ctx.company ? `${ctx.company} · ` : ""}
            {ctx.role}
          </span>
        </div>
      )}

      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        <CrawlStatusChip />
        <button
          type="button"
          onClick={onOpenCommand}
          className="inline-flex items-center gap-2 px-3 py-1.5 text-sm text-[var(--text-secondary)] border border-[var(--border-subtle)] rounded-lg hover:bg-[var(--surface-base)]"
        >
          <Search size={14} />
          <span className="hidden sm:inline">搜索</span>
          <kbd className="hidden sm:inline text-xs px-1.5 py-0.5 bg-[var(--surface-base)] rounded border border-[var(--border-subtle)]">
            ⌘K
          </kbd>
        </button>
      </div>
    </header>
  );
}

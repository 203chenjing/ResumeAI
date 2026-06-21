"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sparkles } from "lucide-react";
import clsx from "clsx";
import { ROUTES } from "@/lib/navigation";

const STEPS = [
  { id: 1, label: "准备", href: ROUTES.studioPrepare },
  { id: 2, label: "改稿", href: ROUTES.studioEdit },
  { id: 3, label: "导出", href: ROUTES.studioExport },
] as const;

export default function StudioHeader() {
  const pathname = usePathname();
  const current =
    pathname.startsWith(ROUTES.studioExport) ? 3
    : pathname.startsWith(ROUTES.studioEdit) ? 2
    : 1;

  return (
    <header className="h-14 border-b border-[var(--border-subtle)] bg-[var(--surface-container)] flex items-center justify-between px-4 shrink-0">
      <Link href="/" className="flex items-center gap-2 text-[var(--primary)] font-semibold text-sm">
        <Sparkles size={16} />
        ResumeAI
      </Link>
      <div className="flex items-center gap-1">
        {STEPS.map((s, i) => (
          <div key={s.id} className="flex items-center gap-1">
            <span
              className={clsx(
                "px-3 py-1 rounded-full text-sm",
                current === s.id
                  ? "bg-[var(--primary)] text-white font-medium"
                  : current > s.id
                    ? "text-[var(--semantic-success)]"
                    : "text-[var(--text-disabled)]"
              )}
            >
              {s.id}. {s.label}
            </span>
            {i < STEPS.length - 1 && (
              <span className="text-[var(--text-disabled)] mx-1">→</span>
            )}
          </div>
        ))}
      </div>
      <Link
        href="/"
        className="text-sm text-[var(--text-secondary)] hover:text-[var(--primary)]"
      >
        退出
      </Link>
    </header>
  );
}

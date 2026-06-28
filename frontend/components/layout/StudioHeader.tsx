"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sparkles } from "lucide-react";
import clsx from "clsx";
import { ROUTES } from "@/lib/navigation";
import { copy } from "@/lib/copy";
import { CrawlStatusChip } from "./CrawlStatusIndicator";

const STEPS = [
  { id: 1, label: copy.nav.steps.prepare, href: ROUTES.studioPrepare },
  { id: 2, label: copy.nav.steps.edit, href: ROUTES.studioEdit },
  { id: 3, label: copy.nav.steps.export, href: ROUTES.studioExport },
] as const;

export default function StudioHeader() {
  const pathname = usePathname();
  const current =
    pathname.startsWith(ROUTES.studioExport) ? 3
    : pathname.startsWith(ROUTES.studioEdit) ? 2
    : 1;

  return (
    <header className="h-14 border-b border-[var(--border-faint)] bg-[var(--surface-container)] flex items-center justify-between px-5 shrink-0">
      <Link href="/" className="flex items-center gap-2 text-[var(--text-primary)] font-medium text-sm hover:text-[var(--primary)] transition-colors">
        <Sparkles size={18} className="text-[var(--primary)]" />
        {copy.product.name}
      </Link>
      <nav className="flex items-center gap-1" aria-label="改稿步骤">
        {STEPS.map((s, i) => {
          const done = current > s.id;
          const active = current === s.id;
          const reachable = current >= s.id;
          return (
            <div key={s.id} className="flex items-center">
              {reachable ? (
                <Link
                  href={s.href}
                  className={clsx(
                    "px-3.5 py-1.5 rounded-[var(--radius-full)] text-sm transition-colors",
                    active && "bg-[var(--primary)] text-white font-medium",
                    done && !active && "text-[var(--primary)] bg-[var(--primary-muted)]",
                  )}
                >
                  {s.label}
                </Link>
              ) : (
                <span className="px-3.5 py-1.5 rounded-[var(--radius-full)] text-sm text-[var(--text-disabled)]">
                  {s.label}
                </span>
              )}
              {i < STEPS.length - 1 && (
                <span className="w-6 h-px bg-[var(--border-subtle)] mx-0.5" aria-hidden />
              )}
            </div>
          );
        })}
      </nav>
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        <CrawlStatusChip />
        <Link href="/" className="btn-ghost text-[var(--text-secondary)] shrink-0">
          {copy.nav.exit}
        </Link>
      </div>
    </header>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  BarChart3,
  BookOpen,
  Briefcase,
  ChevronLeft,
  ChevronRight,
  Home,
  Kanban,
  PenLine,
} from "lucide-react";
import clsx from "clsx";
import { NAV_ITEMS, ROUTES } from "@/lib/navigation";
import { copy } from "@/lib/copy";

const ICONS = {
  home: Home,
  book: BookOpen,
  briefcase: Briefcase,
  tracker: Kanban,
  chart: BarChart3,
  edit: PenLine,
} as const;

const STORAGE_KEY = "resumeai-nav-collapsed";

export default function NavRail({ collapsed: collapsedProp }: { collapsed?: boolean }) {
  const pathname = usePathname();
  const [collapsedInternal, setCollapsedInternal] = useState(false);
  const controlled = collapsedProp !== undefined;
  const collapsed = controlled ? collapsedProp : collapsedInternal;

  useEffect(() => {
    if (controlled) return;
    try {
      setCollapsedInternal(localStorage.getItem(STORAGE_KEY) === "1");
    } catch {
      /* ignore */
    }
  }, [controlled]);

  function toggleCollapsed() {
    const next = !collapsed;
    if (!controlled) {
      setCollapsedInternal(next);
      try {
        localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
    }
  }

  const mainItems = NAV_ITEMS.filter((i) => i.section === "main");
  const studioItem = NAV_ITEMS.find((i) => i.section === "studio");

  function isActive(href: string) {
    if (href === ROUTES.hub) return pathname === "/";
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  function isStudioActive() {
    return pathname.startsWith("/studio");
  }

  return (
    <nav
      className={clsx(
        "flex flex-col border-r border-[var(--border-faint)] bg-[var(--surface-container)] shrink-0 overflow-x-hidden",
        collapsed ? "w-[var(--rail-width-collapsed)]" : "w-[var(--rail-width)]"
      )}
      aria-label="主导航"
    >
      <div className="flex-1 py-3 flex flex-col gap-1 px-2">
        {mainItems.map((item) => {
          const Icon = ICONS[item.icon as keyof typeof ICONS];
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              title={collapsed ? item.label : undefined}
              className={clsx(
                "flex items-center rounded-[var(--radius-sm)] py-2.5 text-sm transition-colors whitespace-nowrap",
                collapsed ? "justify-center px-2" : "gap-3 px-3",
                active
                  ? "bg-[var(--primary-muted)] text-[var(--primary)] font-medium"
                  : "text-[var(--text-secondary)] hover:bg-[var(--surface-base)] hover:text-[var(--text-primary)]"
              )}
            >
              <Icon size={20} className="shrink-0" strokeWidth={active ? 2.25 : 2} />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
      </div>
      {studioItem && (
        <div className="border-t border-[var(--border-subtle)] p-2">
          <Link
            href={studioItem.href}
            title={collapsed ? studioItem.label : undefined}
            className={clsx(
              "flex items-center rounded-[var(--radius-full)] py-2.5 text-sm font-medium transition-colors whitespace-nowrap",
              collapsed ? "justify-center px-2" : "gap-3 px-3 mx-1",
              isStudioActive()
                ? "bg-[var(--primary)] text-white shadow-sm"
                : "text-[var(--text-secondary)] hover:bg-[var(--surface-base)]"
            )}
          >
            <PenLine size={20} className="shrink-0" />
            {!collapsed && <span>{studioItem.label}</span>}
          </Link>
        </div>
      )}
      <div className="border-t border-[var(--border-subtle)] p-2">
        <button
          type="button"
          onClick={toggleCollapsed}
          className={clsx(
            "flex w-full items-center rounded-lg py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-base)] hover:text-[var(--text-primary)] transition-colors",
            collapsed ? "justify-center px-2" : "gap-2 px-3"
          )}
          aria-label={collapsed ? copy.nav.expandRail : copy.nav.collapseRail}
          title={collapsed ? copy.nav.expandRail : copy.nav.collapseRail}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          {!collapsed && <span>{copy.nav.collapseRail}</span>}
        </button>
      </div>
    </nav>
  );
}

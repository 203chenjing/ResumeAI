/** 路由常量与 AppShell 模式判断 */

import { copy } from "./copy";

export const ROUTES = {
  hub: "/",
  assets: "/assets",
  jobs: "/jobs",
  tracker: "/tracker",
  insights: "/insights",
  studioPrepare: "/studio/prepare",
  studioEdit: "/studio/edit",
  studioExport: "/studio/export",
} as const;

export type ShellMode = "hub" | "object" | "studio" | "minimal";

export function getShellMode(pathname: string): ShellMode {
  if (pathname.startsWith("/studio")) return "studio";
  if (pathname.startsWith("/interview") || pathname.startsWith("/jobs/compare")) return "minimal";
  if (pathname === ROUTES.hub) return "hub";
  return "object";
}

export function getStudioStep(pathname: string): 1 | 2 | 3 | null {
  if (pathname.startsWith(ROUTES.studioPrepare)) return 1;
  if (pathname.startsWith(ROUTES.studioEdit)) return 2;
  if (pathname.startsWith(ROUTES.studioExport)) return 3;
  return null;
}

export interface StudioContextChip {
  company: string;
  role: string;
}

export function buildStudioContext(
  jdAnalysis: { company?: string; role?: string } | null
): StudioContextChip | null {
  if (!jdAnalysis?.role) return null;
  return {
    company: jdAnalysis.company || "",
    role: jdAnalysis.role,
  };
}

export interface NavItem {
  href: string;
  label: string;
  icon: string;
  section?: "main" | "studio";
}

export const NAV_ITEMS: NavItem[] = [
  { href: ROUTES.hub, label: copy.nav.hub, icon: "home", section: "main" },
  { href: ROUTES.assets, label: copy.nav.knowledge, icon: "book", section: "main" },
  { href: ROUTES.jobs, label: copy.nav.jobs, icon: "briefcase", section: "main" },
  { href: ROUTES.tracker, label: copy.nav.tracker, icon: "tracker", section: "main" },
  { href: ROUTES.insights, label: copy.nav.insights, icon: "chart", section: "main" },
  { href: ROUTES.studioPrepare, label: copy.nav.studio, icon: "edit", section: "studio" },
];

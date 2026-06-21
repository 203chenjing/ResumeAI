/** 路由常量与 AppShell 模式判断 */

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
  { href: ROUTES.hub, label: "工作台", icon: "home", section: "main" },
  { href: ROUTES.assets, label: "知识库", icon: "book", section: "main" },
  { href: ROUTES.jobs, label: "岗位", icon: "briefcase", section: "main" },
  { href: ROUTES.tracker, label: "投递", icon: "tracker", section: "main" },
  { href: ROUTES.insights, label: "洞察", icon: "chart", section: "main" },
  { href: ROUTES.studioPrepare, label: "改简历", icon: "edit", section: "studio" },
];

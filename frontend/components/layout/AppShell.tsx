"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import NavRail from "./NavRail";
import TopBar from "./TopBar";
import StudioHeader from "./StudioHeader";
import CommandPalette from "./CommandPalette";
import { getShellMode } from "@/lib/navigation";
import { useAppStore } from "@/stores/useAppStore";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const mode = getShellMode(pathname);
  const [cmdOpen, setCmdOpen] = useState(false);
  const copilotOpen = useAppStore((s) => s.copilotOpen);
  const setCopilotOpen = useAppStore((s) => s.setCopilotOpen);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (mode !== "studio" || !pathname.includes("/studio/edit")) return;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "j") {
        e.preventDefault();
        setCopilotOpen(!copilotOpen);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mode, pathname, copilotOpen, setCopilotOpen]);

  if (mode === "minimal") {
    return <>{children}</>;
  }

  if (mode === "studio") {
    return (
      <div className="h-screen flex flex-col bg-[var(--surface-base)]">
        <StudioHeader />
        <main className="flex-1 min-h-0 overflow-hidden">{children}</main>
        <CommandPalette open={cmdOpen} onOpenChange={setCmdOpen} />
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-[var(--surface-base)]">
      <TopBar onOpenCommand={() => setCmdOpen(true)} />
      <div className="flex flex-1 min-h-0">
        <NavRail />
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
      <CommandPalette open={cmdOpen} onOpenChange={setCmdOpen} />
    </div>
  );
}

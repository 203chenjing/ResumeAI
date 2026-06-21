"use client";

import { Suspense } from "react";
import PrepareView from "@/components/studio/PrepareView";

export default function StudioPreparePage() {
  return (
    <Suspense fallback={<div className="p-6 text-[var(--text-secondary)]">加载中…</div>}>
      <PrepareView />
    </Suspense>
  );
}

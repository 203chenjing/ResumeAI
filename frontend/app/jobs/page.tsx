"use client";

import { Suspense } from "react";
import JobsView from "@/components/jobs/JobsView";

export default function JobsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-[var(--text-secondary)]">加载中…</div>}>
      <JobsView />
    </Suspense>
  );
}

"use client";

import Link from "next/link";
import { ArrowRight, PenLine } from "lucide-react";
import { ROUTES } from "@/lib/navigation";
import type { LastStudioMeta } from "@/lib/sessionBootstrap";

export default function ContinueCard({ meta }: { meta: LastStudioMeta }) {
  const hasSession = !!meta.sessionId;
  const stepLabel = meta.step === 1 ? "准备" : meta.step === 3 ? "导出" : "改稿";
  const href =
    meta.step === 3 ? ROUTES.studioExport
    : meta.step === 1 ? ROUTES.studioPrepare
    : ROUTES.studioEdit;

  if (!hasSession) {
    return (
      <div className="p-6 rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-container)]">
        <h2 className="font-semibold text-lg mb-2">开始一次改稿</h2>
        <p className="text-sm text-[var(--text-secondary)] mb-4">上传简历，针对目标 JD 定制一页投递版</p>
        <Link
          href={ROUTES.studioPrepare}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-[var(--primary)] text-white rounded-lg text-sm font-medium"
        >
          <PenLine size={16} /> 新建改稿
        </Link>
      </div>
    );
  }

  return (
    <div className="p-6 rounded-xl border-2 border-[var(--primary-muted)] bg-[var(--surface-container)]">
      <p className="text-xs text-[var(--text-secondary)] uppercase tracking-wide mb-1">继续改稿</p>
      <h2 className="font-semibold text-xl mb-1">
        {meta.company || meta.role || "上次会话"}
        {meta.company && meta.role && (
          <span className="text-[var(--text-secondary)] font-normal text-base"> · {meta.role}</span>
        )}
      </h2>
      <p className="text-sm text-[var(--text-secondary)] mb-4">当前步骤：{stepLabel}</p>
      <Link
        href={href}
        className="inline-flex items-center gap-2 px-5 py-2.5 bg-[var(--primary)] text-white rounded-lg text-sm font-medium"
      >
        继续 <ArrowRight size={16} />
      </Link>
    </div>
  );
}

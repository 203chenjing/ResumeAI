"use client";

import Link from "next/link";
import { ArrowRight, PenLine } from "lucide-react";
import clsx from "clsx";
import { ROUTES } from "@/lib/navigation";
import { copy } from "@/lib/copy";
import type { LastStudioMeta } from "@/lib/sessionBootstrap";
import type { SessionArchive } from "@/lib/types";

interface Props {
  meta: LastStudioMeta;
  archives?: SessionArchive[];
  onSelectArchive?: (item: SessionArchive) => void;
}

function stepHref(step: number) {
  if (step === 3) return ROUTES.studioExport;
  if (step === 1) return ROUTES.studioPrepare;
  return ROUTES.studioEdit;
}

function stepLabel(step: number) {
  if (step === 1) return copy.nav.steps.prepare;
  if (step === 3) return copy.nav.steps.export;
  return copy.nav.steps.edit;
}

function archiveTitle(item: SessionArchive) {
  return item.title || copy.hub.lastSession;
}

function archiveStatus(item: SessionArchive) {
  if (item.finalize_status === "finalized") return "已定稿";
  if (item.pending_suggestions > 0) return `${item.pending_suggestions} 条待处理`;
  return stepLabel(item.suggestions_total > 0 ? 2 : 1);
}

export default function ContinueCard({ meta, archives = [], onSelectArchive }: Props) {
  const primaryArchive =
    archives.find((a) => a.session_id === meta.sessionId) ?? archives[0] ?? null;

  const hasPrimary = !!meta.sessionId || !!primaryArchive;

  if (!hasPrimary) {
    return (
      <div className="hero-card">
        <p className="section-label mb-2">{copy.product.tagline}</p>
        <h2 className="text-xl font-medium text-[var(--text-primary)] mb-1">{copy.hub.newSession}</h2>
        <p className="text-sm text-[var(--text-secondary)] mb-1">{copy.hub.startFresh}</p>
        <p className="text-xs text-[var(--text-disabled)] mb-6">{copy.hub.startFreshHint}</p>
        <Link href={ROUTES.studioPrepare} className="btn-primary">
          <PenLine size={16} />
          {copy.hub.newSession}
        </Link>
      </div>
    );
  }

  const title =
    meta.company && meta.role
      ? `${meta.company} · ${meta.role}`
      : meta.role ||
        meta.company ||
        (primaryArchive ? archiveTitle(primaryArchive) : copy.hub.lastSession);

  const href = meta.sessionId
    ? stepHref(meta.step)
    : primaryArchive
      ? stepHref(
          primaryArchive.finalize_status === "finalized"
            ? 3
            : primaryArchive.suggestions_total > 0
              ? 2
              : 1
        )
      : ROUTES.studioPrepare;

  const progress = meta.sessionId
    ? copy.hub.progress(stepLabel(meta.step))
    : primaryArchive
      ? archiveStatus(primaryArchive)
      : "";

  const chipArchives = archives.filter((a) => a.session_id !== (meta.sessionId || primaryArchive?.session_id));

  return (
    <div className="hero-card border-[var(--primary)]/20">
      <p className="section-label mb-2">{copy.hub.continueEdit}</p>
      <h2 className="text-xl font-medium text-[var(--text-primary)] mb-1">{title}</h2>
      {progress && <p className="text-sm text-[var(--text-secondary)] mb-5">{progress}</p>}
      <Link href={href} className="btn-primary">
        {copy.hub.continueCta}
        <ArrowRight size={16} />
      </Link>

      {chipArchives.length > 0 && onSelectArchive && (
        <div className="mt-5 pt-4 border-t border-[var(--border-faint)]">
          <p className="text-xs text-[var(--text-secondary)] mb-2">{copy.hub.recentArchives}</p>
          <div className="flex flex-wrap gap-2">
            {chipArchives.slice(0, 5).map((item) => (
              <button
                key={item.session_id}
                type="button"
                onClick={() => onSelectArchive(item)}
                className={clsx(
                  "max-w-[12rem] truncate px-3 py-1.5 rounded-[var(--radius-full)] text-xs",
                  "border border-[var(--border-subtle)] bg-[var(--surface-container)]",
                  "text-[var(--text-primary)] hover:border-[var(--primary)] hover:bg-[var(--primary-muted)]/40 transition-colors"
                )}
                title={archiveTitle(item)}
              >
                {archiveTitle(item)}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

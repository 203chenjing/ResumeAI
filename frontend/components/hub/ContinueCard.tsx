"use client";

import Link from "next/link";
import { ArrowRight, PenLine } from "lucide-react";
import { ROUTES } from "@/lib/navigation";
import { copy } from "@/lib/copy";
import type { LastStudioMeta } from "@/lib/sessionBootstrap";

export default function ContinueCard({ meta }: { meta: LastStudioMeta }) {
  const hasSession = !!meta.sessionId;
  const stepLabel =
    meta.step === 1 ? copy.nav.steps.prepare
    : meta.step === 3 ? copy.nav.steps.export
    : copy.nav.steps.edit;
  const href =
    meta.step === 3 ? ROUTES.studioExport
    : meta.step === 1 ? ROUTES.studioPrepare
    : ROUTES.studioEdit;

  if (!hasSession) {
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

  const title = meta.company && meta.role
    ? `${meta.company} · ${meta.role}`
    : meta.role || meta.company || copy.hub.lastSession;

  return (
    <div className="hero-card border-[var(--primary)]/20">
      <p className="section-label mb-2">{copy.hub.continueEdit}</p>
      <h2 className="text-xl font-medium text-[var(--text-primary)] mb-1">{title}</h2>
      <p className="text-sm text-[var(--text-secondary)] mb-6">{copy.hub.progress(stepLabel)}</p>
      <Link href={href} className="btn-primary">
        {copy.common.continue}
        <ArrowRight size={16} />
      </Link>
    </div>
  );
}

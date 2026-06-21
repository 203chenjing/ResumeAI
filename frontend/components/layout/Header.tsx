"use client";

import Link from "next/link";
import { Sparkles } from "lucide-react";
import StepIndicator from "./StepIndicator";
import { ROUTES } from "@/lib/navigation";
import { copy } from "@/lib/copy";

export default function Header({ step }: { step?: 1 | 2 | 3 }) {
  return (
    <header className="bg-[var(--surface-container)] border-b border-[var(--border-subtle)] sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 text-[var(--primary)] font-bold text-lg">
          <Sparkles size={20} /> {copy.product.name}
        </Link>
        {step && <StepIndicator current={step} />}
        <div className="flex items-center gap-4">
          <Link href={ROUTES.assets} className="text-sm text-[var(--text-secondary)] hover:text-[var(--primary)]">
            {copy.nav.knowledge}
          </Link>
          <Link href={ROUTES.jobs} className="text-sm text-[var(--text-secondary)] hover:text-[var(--primary)]">
            {copy.nav.jobs}
          </Link>
          <Link href={ROUTES.tracker} className="text-sm text-[var(--text-secondary)] hover:text-[var(--primary)]">
            {copy.nav.tracker}
          </Link>
          <Link href={ROUTES.insights} className="text-sm text-[var(--text-secondary)] hover:text-[var(--primary)]">
            {copy.nav.insights}
          </Link>
        </div>
      </div>
    </header>
  );
}

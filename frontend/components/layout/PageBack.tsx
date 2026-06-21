"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function PageBack({ href, label }: { href: string; label?: string }) {
  return (
    <Link
      href={href}
      className="inline-flex items-center gap-1 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] mb-4"
    >
      <ArrowLeft size={14} /> {label ?? "返回"}
    </Link>
  );
}

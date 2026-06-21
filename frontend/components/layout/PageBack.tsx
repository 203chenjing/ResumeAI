"use client";

import { useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";

export default function PageBack({
  href,
  label,
}: {
  href?: string;
  label: string;
}) {
  const router = useRouter();

  return (
    <button
      type="button"
      onClick={() => (href ? router.push(href) : router.back())}
      className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900 mb-4"
    >
      <ChevronLeft size={16} />
      {label}
    </button>
  );
}

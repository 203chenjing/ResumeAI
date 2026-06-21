"use client";

import Link from "next/link";
import { Sparkles } from "lucide-react";
import StepIndicator from "./StepIndicator";

export default function Header({ step }: { step?: 1 | 2 | 3 }) {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 text-blue-600 font-bold text-lg">
          <Sparkles size={20} /> ResumeAI
        </Link>
        {step && <StepIndicator current={step} />}
        <div className="flex items-center gap-4">
          <Link href="/knowledge" className="text-sm text-slate-600 hover:text-blue-600">
            知识库
          </Link>
          <Link href="/jobs" className="text-sm text-slate-600 hover:text-blue-600">
            岗位
          </Link>
          <Link href="/tracker" className="text-sm text-slate-600 hover:text-blue-600">
            投递追踪
          </Link>
          <Link href="/insights" className="text-sm text-slate-600 hover:text-blue-600">
            洞察
          </Link>
        </div>
      </div>
    </header>
  );
}

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Briefcase, BookOpen, PenLine } from "lucide-react";
import ContinueCard from "@/components/hub/ContinueCard";
import TodoList from "@/components/hub/TodoList";
import GlanceStats from "@/components/hub/GlanceStats";
import { EMPTY_STUDIO_META, getLastStudioMeta } from "@/lib/sessionBootstrap";
import { ROUTES } from "@/lib/navigation";

export default function HubPage() {
  const [meta, setMeta] = useState(EMPTY_STUDIO_META);

  useEffect(() => {
    setMeta(getLastStudioMeta());
  }, []);

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">工作台</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-1">秋招求职操作系统 · 改简历为主链</p>
      </div>

      <ContinueCard meta={meta} />

      <div className="grid md:grid-cols-2 gap-4">
        <TodoList />
        <div className="p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-container)]">
          <h3 className="text-sm font-semibold mb-3">快捷入口</h3>
          <div className="flex flex-col gap-2">
            <Link href={ROUTES.studioPrepare} className="flex items-center gap-2 text-sm text-[var(--primary)] hover:underline">
              <PenLine size={16} /> 新建改稿
            </Link>
            <Link href={ROUTES.jobs} className="flex items-center gap-2 text-sm text-[var(--primary)] hover:underline">
              <Briefcase size={16} /> 发现岗位
            </Link>
            <Link href={ROUTES.assets} className="flex items-center gap-2 text-sm text-[var(--primary)] hover:underline">
              <BookOpen size={16} /> 整理知识库
            </Link>
          </div>
        </div>
      </div>

      <GlanceStats />
    </div>
  );
}

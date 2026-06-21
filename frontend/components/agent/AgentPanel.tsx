"use client";

import { Bot, CheckCircle2, Loader2, Wrench } from "lucide-react";
import type { AgentStreamEvent } from "@/lib/api";

export type AgentStep = {
  id: string;
  kind: "thought" | "tool_call" | "tool_result" | "done" | "error" | "confirm";
  label: string;
  detail?: string;
  ok?: boolean;
};

const TOOL_LABELS: Record<string, string> = {
  get_state: "读取会话状态",
  save_knowledge_base: "保存知识库",
  analyze_jd: "分析 JD",
  analyze_match: "计算匹配度",
  generate_suggestions: "生成修改建议",
  review_suggestions: "智能审阅建议",
  finalize_resume: "确认定稿",
  finish: "完成任务",
};

export function eventToStep(event: AgentStreamEvent): AgentStep | null {
  if (event.type === "thought") {
    return { id: `t-${event.step}`, kind: "thought", label: "思考", detail: event.content };
  }
  if (event.type === "tool_call") {
    return {
      id: `c-${event.step}-${event.action}`,
      kind: "tool_call",
      label: TOOL_LABELS[event.action] || event.action,
      detail: "执行中…",
    };
  }
  if (event.type === "tool_result") {
    const ok = event.result?.ok !== false;
    const err = event.result?.error as string | undefined;
    const extra = event.result?.overall_score
      ? `匹配度 ${event.result.overall_score}`
      : event.result?.count
        ? `${event.result.count} 条建议`
        : event.result?.accepted !== undefined
          ? `接受 ${event.result.accepted} / 拒绝 ${event.result.rejected}`
          : "";
    return {
      id: `r-${event.step}-${event.action}`,
      kind: "tool_result",
      label: TOOL_LABELS[event.action] || event.action,
      detail: err || extra || (ok ? "完成" : "失败"),
      ok,
    };
  }
  if (event.type === "agent_phase") {
    return { id: `phase-${event.agent}`, kind: "thought", label: `${event.agent} Agent`, detail: event.content };
  }
  if (event.type === "confirmation_required") {
    return { id: "confirm", kind: "confirm", label: "等待确认", detail: event.message, ok: undefined };
  }
  if (event.type === "done") {
    return { id: "done", kind: "done", label: "完成", detail: event.summary, ok: true };
  }
  if (event.type === "error") {
    return { id: "error", kind: "error", label: "错误", detail: event.message, ok: false };
  }
  return null;
}

export default function AgentPanel({
  steps,
  running,
}: {
  steps: AgentStep[];
  running: boolean;
}) {
  if (!steps.length && !running) return null;

  return (
    <section className="mt-6 bg-gradient-to-br from-violet-50 to-white rounded-xl border border-violet-200 p-6">
      <div className="flex items-center gap-2 mb-4">
        <Bot size={18} className="text-violet-600" />
        <h2 className="font-semibold text-lg text-slate-900">Agent 执行过程</h2>
        {running && <Loader2 size={16} className="animate-spin text-violet-500" />}
      </div>
      <ol className="space-y-2">
        {steps.map((s) => (
          <li
            key={s.id}
            className={`flex items-start gap-3 text-sm p-2 rounded-lg ${
              s.kind === "thought" ? "bg-white/60 text-slate-600 italic" : "bg-white"
            }`}
          >
            {s.kind === "tool_call" && <Wrench size={14} className="text-violet-500 mt-0.5 shrink-0" />}
            {s.kind === "tool_result" && (
              <CheckCircle2
                size={14}
                className={`mt-0.5 shrink-0 ${s.ok ? "text-green-500" : "text-red-500"}`}
              />
            )}
            {s.kind === "done" && <CheckCircle2 size={14} className="text-green-600 mt-0.5 shrink-0" />}
            <div>
              <div className="font-medium text-slate-800">{s.label}</div>
              {s.detail && <div className="text-slate-600 text-xs mt-0.5">{s.detail}</div>}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

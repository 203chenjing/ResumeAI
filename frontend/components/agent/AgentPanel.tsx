"use client";

import { Sparkles, CheckCircle2, Loader2, Wrench } from "lucide-react";
import type { AgentStreamEvent } from "@/lib/api";
import { copy } from "@/lib/copy";

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
  analyze_jd: "分析岗位",
  analyze_match: "计算匹配度",
  generate_suggestions: "生成修改建议",
  propose_targeted_edits: "精准定位改稿",
  review_suggestions: "审阅建议",
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
    return { id: `phase-${event.agent}`, kind: "thought", label: event.agent || "助手", detail: event.content };
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
    <section className="surface-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles size={16} className="text-[var(--primary)]" />
        <h2 className="text-sm font-medium text-[var(--text-primary)]">{copy.prepare.pipelineTitle}</h2>
        {running && <Loader2 size={14} className="animate-spin text-[var(--primary)]" />}
      </div>
      <ol className="space-y-2">
        {steps.map((s) => (
          <li
            key={s.id}
            className={`flex items-start gap-3 text-sm p-2 rounded-lg bg-[var(--surface-base)] ${
              s.kind === "thought" ? "italic text-[var(--text-secondary)]" : ""
            }`}
          >
            {s.kind === "tool_call" && <Wrench size={14} className="text-[var(--primary)] mt-0.5 shrink-0" />}
            {s.kind === "tool_result" && (
              <CheckCircle2
                size={14}
                className={`mt-0.5 shrink-0 ${s.ok ? "text-green-600" : "text-[var(--semantic-danger)]"}`}
              />
            )}
            {s.kind === "done" && <CheckCircle2 size={14} className="text-green-600 mt-0.5 shrink-0" />}
            <div>
              <div className="font-medium text-[var(--text-primary)]">{s.label}</div>
              {s.detail && <div className="text-[var(--text-secondary)] text-xs mt-0.5">{s.detail}</div>}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

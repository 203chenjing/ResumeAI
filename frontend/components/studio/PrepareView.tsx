"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Upload,
  FileText,
  Loader2,
  AlertCircle,
  CheckCircle2,
  ShieldAlert,
  Bot,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import AgentPanel, { AgentStep, eventToStep } from "@/components/agent/AgentPanel";
import KnowledgeStatusBar from "@/components/studio/KnowledgeStatusBar";
import { api, AgentStreamEvent } from "@/lib/api";
import { useAppStore, type DensityInfo, type FinalizeStatus } from "@/stores/useAppStore";
import { buildOrchestrateGoal, getClientId, loadLocalMemory, saveLocalMemory } from "@/lib/userMemory";
import { persistSessionId, persistStudioMeta } from "@/lib/sessionBootstrap";
import MatchRadar from "@/components/match/MatchRadar";
import GapAnalysisList from "@/components/match/GapAnalysisList";
import ApplicationDecisionCard, { type ApplicationDecision } from "@/components/match/ApplicationDecision";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import { ROUTES } from "@/lib/navigation";

export default function PrepareView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    sessionId,
    setSessionId,
    parsedResume,
    setParsedResume,
    setOriginalMarkdown,
    setCurrentMarkdown,
    jdText,
    setJdText,
    jdAnalysis,
    setJdAnalysis,
    setMatchResult,
    setSuggestions,
    matchResult,
    knowledgeBase,
    setKnowledgeBase,
    setDensity,
    setFinalizeStatus,
    loading,
    setLoading,
    pushToast,
    reset,
    studioFromJob,
    setStudioFromJob,
  } = useAppStore();

  const [fileName, setFileName] = useState("");
  const [error, setError] = useState("");
  const [progress, setProgress] = useState("");
  const [agentRunning, setAgentRunning] = useState(false);
  const [agentSteps, setAgentSteps] = useState<AgentStep[]>([]);
  const [agentOpen, setAgentOpen] = useState(false);
  const [matchOpen, setMatchOpen] = useState(false);
  const [agentConfirm, setAgentConfirm] = useState<{
    action: string;
    input?: Record<string, unknown>;
    message: string;
  } | null>(null);
  const [decision, setDecision] = useState<ApplicationDecision | null>(null);

  useEffect(() => {
    persistStudioMeta({ step: 1, sessionId });
  }, [sessionId]);

  useEffect(() => {
    const local = loadLocalMemory();
    api.getUserMemory(getClientId()).then((res) => {
      const kb = (res.data as { knowledge_base_md?: string })?.knowledge_base_md || local.knowledge_base_md;
      if (kb) setKnowledgeBase(kb);
    }).catch(() => {
      if (local.knowledge_base_md) setKnowledgeBase(local.knowledge_base_md);
    });
  }, [setKnowledgeBase]);

  useEffect(() => {
    if (searchParams.get("from") === "job" && studioFromJob) {
      const j = studioFromJob;
      setJdText(j.jd_text || "");
      if (j.company || j.role) {
        setJdAnalysis({
          role: j.role,
          company: j.company,
          archetype: "",
          core_requirements: [],
          preferred_requirements: [],
          keywords: j.tags || [],
          soft_skills: [],
          industry_terms: [],
          legitimacy_score: 100,
          legitimacy_flags: [],
          ranking: {},
        });
      }
    }
  }, [searchParams, studioFromJob, setJdText, setJdAnalysis]);

  async function onFileSelect(file: File) {
    if (file.size > 10 * 1024 * 1024) {
      setError("文件超过 10MB");
      return;
    }
    setError("");
    setFileName(file.name);
    setLoading(true);
    setProgress("正在解析简历...");
    try {
      const res = await api.parseResume(file);
      if (!res.success || !res.data) throw new Error(res.error || "解析失败");
      setSessionId(res.data.session_id);
      persistSessionId(res.data.session_id);
      persistStudioMeta({ sessionId: res.data.session_id, step: 1 });
      setParsedResume(res.data.parsed);
      setOriginalMarkdown(res.data.markdown);
      setCurrentMarkdown(res.data.markdown);
      pushToast("简历解析完成", "success");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
      setProgress("");
    }
  }

  async function onAnalyzeJD() {
    if (!sessionId) {
      setError("请先上传简历");
      return;
    }
    if (jdText.trim().length < 50) {
      setError("JD 内容过短");
      return;
    }
    setLoading(true);
    setProgress("正在分析 JD...");
    try {
      const res = await api.analyzeJD(sessionId, jdText);
      if (!res.success || !res.data) throw new Error(res.error || "JD 分析失败");
      setJdAnalysis(res.data.analysis);
      const m = await api.analyzeMatch(sessionId);
      if (m.success && m.data) {
        setMatchResult(m.data.match);
        if (m.data.decision) setDecision(m.data.decision as ApplicationDecision);
      }
      persistStudioMeta({
        sessionId,
        step: 1,
        company: res.data.analysis.company,
        role: res.data.analysis.role,
      });
      pushToast("JD 分析完成", "success");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
      setProgress("");
    }
  }

  function applyAgentSession(event: AgentStreamEvent) {
    if (event.type !== "done" || !event.session) return;
    const s = event.session;
    if (s.jd_analysis) setJdAnalysis(s.jd_analysis);
    if (s.match) setMatchResult(s.match);
    if (s.suggestions) setSuggestions(s.suggestions);
    if (s.current_resume_md) setCurrentMarkdown(s.current_resume_md);
    if (s.density) setDensity(s.density as DensityInfo);
    if (s.finalize_status) setFinalizeStatus(s.finalize_status as FinalizeStatus);
  }

  async function onAgentRun(confirmed = false) {
    if (!sessionId || jdText.trim().length < 50) {
      setError("请先上传简历并填写 JD");
      return;
    }
    setAgentRunning(true);
    if (!confirmed) setAgentSteps([]);
    await api.streamAgent(
      {
        session_id: sessionId,
        jd_text: jdText,
        knowledge_base: knowledgeBase,
        client_id: getClientId(),
        use_multi_agent: true,
        confirmed,
        confirmed_action:
          agentConfirm && confirmed
            ? { action: agentConfirm.action, action_input: agentConfirm.input }
            : undefined,
        goal: buildOrchestrateGoal(loadLocalMemory()),
      },
      (event) => {
        if (event.type === "agent_phase") {
          setAgentSteps((prev) => [
            ...prev,
            { id: `ph-${event.agent}`, kind: "thought", label: event.agent || "agent", detail: event.content },
          ]);
        }
        const step = eventToStep(event);
        if (step) setAgentSteps((prev) => [...prev, step]);
        if (event.type === "confirmation_required") {
          setAgentConfirm({ action: event.action, input: event.input, message: event.message });
          setAgentRunning(false);
        }
        if (event.type === "done" && event.session) {
          applyAgentSession(event);
          pushToast(event.summary || "Agent 已完成", "success");
          setAgentRunning(false);
          setAgentConfirm(null);
          router.push(ROUTES.studioEdit);
        }
      },
      (err) => {
        setError(err.message);
        setAgentRunning(false);
      }
    );
  }

  async function onStartEdit() {
    if (!sessionId || !jdAnalysis) {
      setError("请先完成简历和 JD 解析");
      return;
    }
    setLoading(true);
    setError("");
    try {
      if (knowledgeBase.trim()) await api.saveKnowledgeBase(sessionId, knowledgeBase);
      const s = await api.generateSuggestions(sessionId, knowledgeBase);
      if (!s.success || !s.data) throw new Error(s.error || "建议生成失败");
      setSuggestions(s.data.suggestions);
      if (s.data.density) setDensity(s.data.density as DensityInfo);
      persistStudioMeta({ sessionId, step: 2, company: jdAnalysis.company, role: jdAnalysis.role });
      pushToast(`已生成 ${s.data.suggestions.length} 条建议`, "success");
      router.push(ROUTES.studioEdit);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
  <div className="h-full overflow-auto p-4 md:p-6 max-w-5xl mx-auto">
    <ConfirmDialog
      open={!!agentConfirm}
      title="Agent 需要您的确认"
      message={agentConfirm?.message || ""}
      confirmLabel="确认继续"
      onConfirm={() => onAgentRun(true)}
      onCancel={() => setAgentConfirm(null)}
    />

    <div className="flex items-center justify-between mb-4">
      <h1 className="text-lg font-semibold">准备：简历与 JD</h1>
      <button type="button" onClick={reset} className="text-sm text-[var(--text-secondary)] hover:underline">
        重新开始
      </button>
    </div>

    <div className="mb-4">
      <KnowledgeStatusBar />
    </div>

    <div className="grid md:grid-cols-2 gap-4">
      <section className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-container)] p-4">
        <h2 className="font-medium mb-3 flex items-center gap-2">
          <Upload size={16} /> 上传简历
        </h2>
        <FileDropzone onFile={onFileSelect} />
        {fileName && (
          <p className="mt-2 text-sm text-[var(--text-secondary)] flex items-center gap-1">
            <FileText size={14} /> {fileName}
          </p>
        )}
        {parsedResume && (
          <div className="mt-3 p-3 rounded-lg bg-green-50 text-sm text-green-800">
            <CheckCircle2 size={14} className="inline mr-1" />
            {parsedResume.header.name || "已解析"} · 教育 {parsedResume.education.length} · 实习{" "}
            {parsedResume.experience.length}
          </div>
        )}
      </section>

      <section className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-container)] p-4">
        <h2 className="font-medium mb-3">目标 JD</h2>
        <textarea
          className="w-full h-48 p-3 border border-[var(--border-subtle)] rounded-lg text-sm font-mono"
          placeholder="粘贴岗位 JD（≥ 50 字）..."
          value={jdText}
          onChange={(e) => setJdText(e.target.value)}
          disabled={loading}
        />
        <button
          type="button"
          onClick={onAnalyzeJD}
          disabled={loading || !sessionId || jdText.trim().length < 50}
          className="mt-2 px-4 py-2 bg-[var(--primary)] text-white rounded-lg text-sm disabled:opacity-40"
        >
          分析 JD
        </button>
        {jdAnalysis && (
          <div className="mt-3 text-sm space-y-2">
            <p className="font-medium text-[var(--primary)]">
              {jdAnalysis.role} {jdAnalysis.company && `· ${jdAnalysis.company}`}
            </p>
            {jdAnalysis.legitimacy_score < 80 && (
              <p className="text-[var(--semantic-warning)] flex items-center gap-1">
                <ShieldAlert size={14} /> 真实性 {jdAnalysis.legitimacy_score}/100
              </p>
            )}
          </div>
        )}
      </section>
    </div>

    {matchResult && (
      <section className="mt-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-container)] p-4">
        <button
          type="button"
          className="w-full flex items-center justify-between font-medium"
          onClick={() => setMatchOpen(!matchOpen)}
        >
          <span>
            匹配度 {matchResult.overall_score}/100
            {decision && ` · ${decision.label}`}
          </span>
          {matchOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </button>
        {matchOpen && (
          <div className="mt-4 grid md:grid-cols-2 gap-4">
            <MatchRadar dimensions={matchResult.dimensions} overallScore={matchResult.overall_score} />
            <div>
              {decision && <ApplicationDecisionCard decision={decision} />}
              <GapAnalysisList gaps={matchResult.gap_analysis.slice(0, 5)} />
            </div>
          </div>
        )}
      </section>
    )}

    {error && (
      <div className="mt-4 p-3 rounded-lg bg-red-50 text-red-700 text-sm flex gap-2">
        <AlertCircle size={16} /> {error}
      </div>
    )}
    {progress && (
      <div className="mt-4 p-3 rounded-lg bg-blue-50 text-blue-700 text-sm flex gap-2">
        <Loader2 size={16} className="animate-spin" /> {progress}
      </div>
    )}

    <section className="mt-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-container)]">
      <button
        type="button"
        className="w-full flex items-center justify-between p-4 font-medium text-sm"
        onClick={() => setAgentOpen(!agentOpen)}
      >
        <span className="flex items-center gap-2">
          <Bot size={16} /> Agent 自动编排（可选）
        </span>
        {agentOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>
      {agentOpen && (
        <div className="px-4 pb-4">
          <AgentPanel steps={agentSteps} running={agentRunning} />
        </div>
      )}
    </section>

    <div className="mt-6 flex flex-wrap justify-end gap-3 pb-6">
      <button
        type="button"
        onClick={() => onAgentRun()}
        disabled={loading || agentRunning || !sessionId || jdText.trim().length < 50}
        className="px-5 py-2.5 rounded-lg border border-[var(--border-subtle)] text-sm"
      >
        Agent 一键改稿
      </button>
      <button
        type="button"
        onClick={onStartEdit}
        disabled={loading || !sessionId || !jdAnalysis}
        className="px-6 py-2.5 bg-[var(--primary)] text-white rounded-lg font-medium disabled:opacity-40"
      >
        开始改稿 →
      </button>
    </div>
  </div>
  );
}

function FileDropzone({ onFile }: { onFile: (f: File) => void }) {
  const [hover, setHover] = useState(false);
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setHover(true);
      }}
      onDragLeave={() => setHover(false)}
      onDrop={(e) => {
        e.preventDefault();
        setHover(false);
        const f = e.dataTransfer.files[0];
        if (f) onFile(f);
      }}
      className={`border-2 border-dashed rounded-lg p-6 text-center text-sm ${
        hover ? "border-[var(--primary)] bg-[var(--primary-muted)]" : "border-[var(--border-subtle)]"
      }`}
    >
      <Upload className="mx-auto mb-2 text-[var(--text-disabled)]" size={28} />
      <label className="text-[var(--primary)] cursor-pointer hover:underline">
        选择文件
        <input
          type="file"
          accept=".pdf,.docx,.md,.txt,.markdown"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onFile(f);
          }}
        />
      </label>
      <p className="text-xs text-[var(--text-disabled)] mt-1">PDF / DOCX / MD / TXT</p>
    </div>
  );
}

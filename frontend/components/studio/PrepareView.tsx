"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Upload,
  FileText,
  Loader2,
  AlertCircle,
  CheckCircle2,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  Sparkles,
} from "lucide-react";
import ThinkChainPanel, { type ThinkStep } from "@/components/studio/ThinkChainPanel";
import KnowledgeStatusBar from "@/components/studio/KnowledgeStatusBar";
import { api } from "@/lib/api";
import { useAppStore, type DensityInfo } from "@/stores/useAppStore";
import { getClientId, loadLocalMemory } from "@/lib/userMemory";
import { persistSessionId, persistStudioMeta } from "@/lib/sessionBootstrap";
import MatchRadar from "@/components/match/MatchRadar";
import GapAnalysisList from "@/components/match/GapAnalysisList";
import ApplicationDecisionCard, { type ApplicationDecision } from "@/components/match/ApplicationDecision";
import { ROUTES } from "@/lib/navigation";
import { copy } from "@/lib/copy";

function initialPipelineSteps(): ThinkStep[] {
  return [
    { id: "analyze_jd", label: copy.prepare.stepAnalyzeJd, status: "pending" },
    { id: "match", label: copy.prepare.stepMatch, status: "pending" },
    { id: "suggestions", label: copy.prepare.stepSuggestions, status: "pending" },
  ];
}

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
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [pipelineSteps, setPipelineSteps] = useState<ThinkStep[]>([]);
  const [matchOpen, setMatchOpen] = useState(false);
  const [decision, setDecision] = useState<ApplicationDecision | null>(null);

  const patchStep = useCallback((id: string, patch: Partial<ThinkStep>) => {
    setPipelineSteps((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  }, []);

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
      setError("文件不能超过 10MB");
      return;
    }
    setError("");
    setFileName(file.name);
    setLoading(true);
    setProgress("正在读取简历…");
    try {
      const res = await api.parseResume(file);
      if (!res.success || !res.data) throw new Error(res.error || "解析失败");
      setSessionId(res.data.session_id);
      persistSessionId(res.data.session_id);
      persistStudioMeta({ sessionId: res.data.session_id, step: 1 });
      setParsedResume(res.data.parsed);
      setOriginalMarkdown(res.data.markdown);
      setCurrentMarkdown(res.data.markdown);
      pushToast("简历已读取", "success");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
      setProgress("");
    }
  }

  async function onAnalyzeJD() {
    if (!sessionId) {
      setError(copy.prepare.uploadFirst);
      return;
    }
    if (jdText.trim().length < 50) {
      setError(copy.prepare.jdTooShort);
      return;
    }
    setLoading(true);
    setProgress("正在分析岗位…");
    try {
      const res = await api.analyzeJD(sessionId, jdText);
      if (!res.success || !res.data) throw new Error(res.error || "岗位分析未完成");
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
      pushToast("岗位分析完成", "success");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
      setProgress("");
    }
  }

  async function onOneClickEdit() {
    if (!sessionId) {
      setError(copy.prepare.uploadFirst);
      return;
    }
    if (jdText.trim().length < 50) {
      setError(copy.prepare.needJdText);
      return;
    }

    setError("");
    setPipelineRunning(true);
    setPipelineSteps(initialPipelineSteps());

    let analysis = jdAnalysis;

    try {
      patchStep("analyze_jd", { status: "running", detail: "正在读懂岗位要求…" });
      if (!analysis) {
        const res = await api.analyzeJD(sessionId, jdText);
        if (!res.success || !res.data) throw new Error(res.error || "岗位分析未完成");
        analysis = res.data.analysis;
        setJdAnalysis(analysis);
        patchStep("analyze_jd", {
          status: "done",
          detail: `${analysis.role}${analysis.company ? ` · ${analysis.company}` : ""}`,
        });
      } else {
        patchStep("analyze_jd", {
          status: "done",
          detail: `${analysis.role}${analysis.company ? ` · ${analysis.company}` : ""}（已分析）`,
        });
      }

      patchStep("match", { status: "running", detail: "对照简历与岗位要求…" });
      const m = await api.analyzeMatch(sessionId);
      if (!m.success || !m.data) throw new Error(m.error || "匹配度计算失败");
      setMatchResult(m.data.match);
      if (m.data.decision) setDecision(m.data.decision as ApplicationDecision);
      patchStep("match", {
        status: "done",
        detail: `匹配度 ${m.data.match.overall_score}/100${
          m.data.decision?.label ? ` · ${m.data.decision.label}` : ""
        }`,
      });

      patchStep("suggestions", { status: "running", detail: "结合知识库与岗位生成建议…" });
      if (knowledgeBase.trim()) {
        await api.saveKnowledgeBase(sessionId, knowledgeBase);
      }
      const s = await api.generateSuggestions(sessionId, knowledgeBase);
      if (!s.success || !s.data) throw new Error(s.error || "建议生成失败，请重试");
      setSuggestions(s.data.suggestions);
      if (s.data.density) setDensity(s.data.density as DensityInfo);

      patchStep("suggestions", {
        status: "done",
        detail: `共 ${s.data.suggestions.length} 条，进入改稿页逐条确认`,
      });

      persistStudioMeta({
        sessionId,
        step: 2,
        company: analysis?.company,
        role: analysis?.role,
      });
      pushToast(copy.edit.syncSuggestions(s.data.suggestions.length), "success");

      await new Promise((r) => setTimeout(r, 400));
      router.push(ROUTES.studioEdit);
    } catch (e) {
      const msg = (e as Error).message;
      setError(msg);
      setPipelineSteps((prev) => {
        const running = prev.find((s) => s.status === "running");
        if (running) {
          return prev.map((s) =>
            s.id === running.id ? { ...s, status: "error", detail: msg } : s
          );
        }
        return prev;
      });
    } finally {
      setPipelineRunning(false);
    }
  }

  const canOneClick = !!sessionId && jdText.trim().length >= 50 && !pipelineRunning && !loading;

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-4xl mx-auto px-4 md:px-6 py-6 pb-28">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="page-title">{copy.prepare.title}</h1>
            <p className="page-subtitle">{copy.prepare.oneClickHint}</p>
          </div>
          <button type="button" onClick={reset} className="btn-ghost">
            {copy.prepare.restart}
          </button>
        </div>

        <div className="mb-5">
          <KnowledgeStatusBar />
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <section className="section-card">
            <h2 className="text-sm font-medium text-[var(--text-primary)] mb-4 flex items-center gap-2">
              <Upload size={16} className="text-[var(--primary)]" />
              {copy.prepare.upload}
            </h2>
            <FileDropzone onFile={onFileSelect} />
            {fileName && (
              <p className="mt-3 text-sm text-[var(--text-secondary)] flex items-center gap-1.5">
                <FileText size={14} /> {fileName}
              </p>
            )}
            {parsedResume && (
              <div className="mt-3 px-3 py-2 rounded-[var(--radius-sm)] bg-[var(--semantic-success)]/10 text-sm text-[var(--semantic-success)] flex items-center gap-1.5">
                <CheckCircle2 size={14} />
                {copy.prepare.parsedSummary(
                  parsedResume.header.name || copy.prepare.parsed,
                  parsedResume.education.length,
                  parsedResume.experience.length
                )}
              </div>
            )}
          </section>

          <section className="section-card">
            <h2 className="text-sm font-medium text-[var(--text-primary)] mb-4">{copy.prepare.jdTitle}</h2>
            <textarea
              className="input-field h-44 font-mono resize-none"
              placeholder={copy.prepare.jdPlaceholder}
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              disabled={loading || pipelineRunning}
            />
            {jdAnalysis && (
              <div className="mt-3 text-sm space-y-1">
                <p className="font-medium text-[var(--text-primary)]">
                  {jdAnalysis.role}
                  {jdAnalysis.company && <span className="text-[var(--text-secondary)] font-normal"> · {jdAnalysis.company}</span>}
                </p>
                {jdAnalysis.legitimacy_score < 80 && (
                  <p className="text-[var(--semantic-warning)] flex items-center gap-1 text-xs">
                    <ShieldAlert size={12} />
                    {copy.prepare.legitimacyWarn(jdAnalysis.legitimacy_score)}
                  </p>
                )}
              </div>
            )}
            {!matchResult && sessionId && jdText.trim().length >= 50 && (
              <button
                type="button"
                onClick={onAnalyzeJD}
                disabled={loading || pipelineRunning}
                className="mt-3 text-link"
              >
                {loading ? copy.common.loading : copy.prepare.analyzeJd}
              </button>
            )}
          </section>
        </div>

        {matchResult && (
          <section className="mt-4 section-card">
            <button
              type="button"
              className="w-full flex items-center justify-between text-sm font-medium"
              onClick={() => setMatchOpen(!matchOpen)}
            >
              <span className="flex items-center gap-2">
                <span className="chip-primary">{copy.prepare.matchScore(matchResult.overall_score)}</span>
                {decision && <span className="text-[var(--text-secondary)]">{decision.label}</span>}
              </span>
              {matchOpen ? <ChevronUp size={18} className="text-[var(--text-secondary)]" /> : <ChevronDown size={18} className="text-[var(--text-secondary)]" />}
            </button>
            {matchOpen && (
              <div className="mt-5 pt-5 border-t border-[var(--border-faint)] grid md:grid-cols-2 gap-5">
                <MatchRadar dimensions={matchResult.dimensions} overallScore={matchResult.overall_score} />
                <div>
                  {decision && <ApplicationDecisionCard decision={decision} />}
                  <GapAnalysisList gaps={matchResult.gap_analysis.slice(0, 5)} />
                </div>
              </div>
            )}
          </section>
        )}

        {(pipelineSteps.length > 0 || pipelineRunning) && (
          <div className="mt-4">
            <ThinkChainPanel title={copy.prepare.pipelineTitle} steps={pipelineSteps} running={pipelineRunning} />
          </div>
        )}

        {error && (
          <div className="mt-4 alert-error">
            <AlertCircle size={16} className="shrink-0 mt-0.5" /> {error}
          </div>
        )}
        {progress && (
          <div className="mt-4 alert-info">
            <Loader2 size={16} className="shrink-0 animate-spin" /> {progress}
          </div>
        )}
      </div>

      <div className="sticky-cta">
        <div className="max-w-4xl mx-auto flex items-center justify-between gap-4">
          <p className="text-xs text-[var(--text-secondary)] hidden sm:block">{copy.prepare.oneClickHint}</p>
          <button
            type="button"
            onClick={onOneClickEdit}
            disabled={!canOneClick}
            className="btn-primary ml-auto"
          >
            {pipelineRunning ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Sparkles size={16} />
            )}
            {copy.prepare.oneClickEdit}
          </button>
        </div>
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
      className={`dropzone ${hover ? "dropzone-active" : "dropzone-idle"}`}
    >
      <Upload className="mx-auto mb-3 text-[var(--text-disabled)]" size={24} />
      <label className="text-[var(--primary)] font-medium cursor-pointer hover:underline">
        {copy.prepare.uploadHint}
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
      <p className="text-xs text-[var(--text-disabled)] mt-2">PDF · DOCX · MD · TXT</p>
    </div>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Download, Loader2, PanelRightClose, PanelRightOpen } from "lucide-react";
import ResumePreview from "@/components/edit/ResumePreview";
import SuggestionPanel from "@/components/edit/SuggestionPanel";
import ChatPanel from "@/components/edit/ChatPanel";
import { useAppStore } from "@/stores/useAppStore";
import { api } from "@/lib/api";
import { persistStudioMeta } from "@/lib/sessionBootstrap";
import { ROUTES } from "@/lib/navigation";

export default function EditView() {
  const router = useRouter();
  const {
    sessionId,
    currentMarkdown,
    finalizedMarkdown,
    finalizeStatus,
    setCurrentMarkdown,
    setSuggestions,
    setMatchResult,
    setFinalizedMarkdown,
    setFinalizeStatus,
    setDensity,
    suggestions,
    jdAnalysis,
    matchResult,
    density,
    copilotOpen,
    setCopilotOpen,
  } = useAppStore();

  useEffect(() => {
    if (!sessionId) {
      router.replace(ROUTES.studioPrepare);
      return;
    }
    persistStudioMeta({
      sessionId,
      step: 2,
      company: jdAnalysis?.company,
      role: jdAnalysis?.role,
    });
    api.getSession(sessionId).then((res) => {
      if (!res.success || !res.data) return;
      const d = res.data;
      if (typeof d.current_resume_md === "string") setCurrentMarkdown(d.current_resume_md);
      if (Array.isArray(d.suggestions)) setSuggestions(d.suggestions as typeof suggestions);
      if (d.match_result) setMatchResult(d.match_result as typeof matchResult);
      if (typeof d.finalized_resume_md === "string") setFinalizedMarkdown(d.finalized_resume_md);
      if (d.finalize_status) setFinalizeStatus(d.finalize_status as typeof finalizeStatus);
      if (typeof d.current_resume_md === "string" && d.current_resume_md.length < 1500) {
        setDensity({
          char_count: d.current_resume_md.length,
          status: "sparse",
          message: `工作稿约 ${d.current_resume_md.length} 字，偏少`,
        });
      }
    }).catch(() => {});
  }, [
    sessionId,
    router,
    jdAnalysis?.company,
    jdAnalysis?.role,
    setCurrentMarkdown,
    setSuggestions,
    setMatchResult,
    setFinalizedMarkdown,
    setFinalizeStatus,
    setDensity,
    suggestions,
    matchResult,
    finalizeStatus,
  ]);

  if (!sessionId) return null;

  const accepted = suggestions.filter((s) => s.status === "accepted").length;
  const showFinalized = finalizeStatus === "finalized" && !!finalizedMarkdown;
  const previewMarkdown = showFinalized ? finalizedMarkdown : currentMarkdown;

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="shrink-0 px-4 py-2 border-b border-[var(--border-subtle)] bg-[var(--surface-container)] flex flex-wrap items-center gap-3 text-sm">
        {jdAnalysis && (
          <span className="font-medium text-[var(--text-primary)]">
            {jdAnalysis.role}
            {jdAnalysis.company && (
              <span className="text-[var(--text-secondary)]"> · {jdAnalysis.company}</span>
            )}
          </span>
        )}
        {matchResult && (
          <span className="text-[var(--text-secondary)]">
            匹配 <span className="font-semibold text-[var(--primary)]">{matchResult.overall_score}</span>
          </span>
        )}
        <span className="text-[var(--text-secondary)]">
          已接受 {accepted}/{suggestions.length}
        </span>
        {density && (
          <span className="text-xs px-2 py-0.5 rounded bg-[var(--surface-base)] text-[var(--text-secondary)]">
            {density.char_count} 字
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => setCopilotOpen(!copilotOpen)}
            className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--surface-base)]"
            title="⌘J 切换 Copilot"
          >
            {copilotOpen ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
            Copilot
          </button>
          <button
            type="button"
            onClick={() => router.push(ROUTES.studioExport)}
            className="inline-flex items-center gap-2 px-4 py-1.5 bg-[var(--primary)] text-white rounded-lg text-sm font-medium hover:opacity-90"
          >
            <Download size={14} /> 前往导出
          </button>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-12 min-h-0 overflow-hidden">
        <div className="col-span-5 overflow-auto border-r border-[var(--border-subtle)] bg-[var(--surface-container)]">
          <ResumePreview markdown={previewMarkdown} finalized={showFinalized} sessionId={sessionId} />
        </div>
        <div className={`overflow-hidden border-r border-[var(--border-subtle)] ${copilotOpen ? "col-span-4" : "col-span-7"}`}>
          <SuggestionPanel />
        </div>
        {copilotOpen && (
          <div className="col-span-3 overflow-hidden min-h-0">
            <ChatPanel />
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, BookOpen, Download, Loader2, PanelRightClose, PanelRightOpen } from "lucide-react";
import ResumePreview from "@/components/edit/ResumePreview";
import SuggestionPanel from "@/components/edit/SuggestionPanel";
import ChatPanel from "@/components/edit/ChatPanel";
import { useAppStore, type DensityInfo } from "@/stores/useAppStore";
import { api } from "@/lib/api";
import { persistStudioMeta } from "@/lib/sessionBootstrap";
import { ROUTES } from "@/lib/navigation";
import { copy } from "@/lib/copy";
import { getClientId, loadLocalMemory } from "@/lib/userMemory";

export default function EditView() {
  const router = useRouter();
  const [buildingFromKb, setBuildingFromKb] = useState(false);
  const [kbNotice, setKbNotice] = useState("");
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
    setKnowledgeBase,
    knowledgeBase,
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
      if (typeof d.knowledge_base_md === "string" && d.knowledge_base_md.trim()) {
        setKnowledgeBase(d.knowledge_base_md);
      }
      if (typeof d.current_resume_md === "string" && d.current_resume_md.length < 1500) {
        setDensity({
          char_count: d.current_resume_md.length,
          status: "sparse",
          message: `内容约 ${d.current_resume_md.length} 字，偏少，建议补充经历`,
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
    setKnowledgeBase,
  ]);

  useEffect(() => {
    if (!sessionId) return;
    api.getKnowledgeBase(sessionId).then((res) => {
      if (res.success && res.data?.content?.trim()) {
        setKnowledgeBase(res.data.content);
      }
    }).catch(() => {});
    const localKb = loadLocalMemory().knowledge_base_md;
    if (localKb.trim()) setKnowledgeBase(localKb);
  }, [sessionId, setKnowledgeBase]);

  const handleBuildFromKb = useCallback(async () => {
    if (!sessionId || buildingFromKb) return;
    const kb =
      knowledgeBase.trim() ||
      loadLocalMemory().knowledge_base_md.trim();
    if (!kb) {
      setKbNotice(copy.edit.kbEmpty);
      return;
    }
    if (!jdAnalysis) {
      setKbNotice(copy.prepare.needBoth);
      return;
    }
    setBuildingFromKb(true);
    setKbNotice("");
    try {
      const res = await api.buildResumeFromKnowledge({
        session_id: sessionId,
        knowledge_base: kb,
        client_id: getClientId(),
        regenerate_suggestions: true,
      });
      if (!res.success || !res.data) {
        throw new Error(res.error || copy.edit.buildFromKbFail);
      }
      const d = res.data;
      setCurrentMarkdown(d.markdown);
      setKnowledgeBase(d.knowledge_base_md || kb);
      if (d.suggestions) setSuggestions(d.suggestions);
      if (d.match) setMatchResult(d.match);
      if (d.density) setDensity(d.density as DensityInfo);
      if (d.finalize_status) setFinalizeStatus(d.finalize_status as typeof finalizeStatus);
      setKbNotice(copy.edit.buildFromKbOk(d.suggestions_count));
    } catch (e) {
      setKbNotice((e as Error).message || copy.edit.buildFromKbFail);
    } finally {
      setBuildingFromKb(false);
    }
  }, [
    sessionId,
    buildingFromKb,
    knowledgeBase,
    jdAnalysis,
    setCurrentMarkdown,
    setKnowledgeBase,
    setSuggestions,
    setMatchResult,
    setDensity,
    setFinalizeStatus,
  ]);

  if (!sessionId) return null;

  const accepted = suggestions.filter((s) => s.status === "accepted").length;
  const showFinalized = finalizeStatus === "finalized" && !!finalizedMarkdown;
  const previewMarkdown = showFinalized ? finalizedMarkdown : currentMarkdown;

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="toolbar">
        {jdAnalysis && (
          <span className="text-sm font-medium text-[var(--text-primary)] truncate max-w-[200px]">
            {jdAnalysis.role}
            {jdAnalysis.company && (
              <span className="text-[var(--text-secondary)] font-normal"> · {jdAnalysis.company}</span>
            )}
          </span>
        )}
        {matchResult && (
          <span className="chip-primary">
            {copy.edit.match(matchResult.overall_score)}
          </span>
        )}
        <span className="chip">
          {copy.edit.accepted(accepted, suggestions.length)}
        </span>
        {density && (
          <span className="chip">{copy.edit.chars(density.char_count)}</span>
        )}
        {kbNotice && (
          <span className="text-xs text-[var(--text-secondary)] max-w-xs truncate" title={kbNotice}>
            {kbNotice}
          </span>
        )}
        <div className="ml-auto flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleBuildFromKb}
            disabled={buildingFromKb || !jdAnalysis}
            title={copy.edit.buildFromKb}
            className="btn-secondary text-xs py-1.5"
          >
            {buildingFromKb ? <Loader2 size={14} className="animate-spin" /> : <BookOpen size={14} />}
            {buildingFromKb ? copy.edit.buildFromKbLoading : copy.edit.buildFromKb}
          </button>
          <Link href={ROUTES.studioPrepare} className="btn-secondary text-xs py-1.5">
            <ArrowLeft size={14} /> {copy.edit.backPrepare}
          </Link>
          <button
            type="button"
            onClick={() => setCopilotOpen(!copilotOpen)}
            className="btn-secondary text-xs py-1.5"
            title={copy.edit.assistantHint}
          >
            {copilotOpen ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
            {copy.edit.assistant}
          </button>
          <button
            type="button"
            onClick={() => router.push(ROUTES.studioExport)}
            className="btn-primary text-xs py-1.5"
          >
            <Download size={14} /> {copy.export.title}
          </button>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-12 min-h-0 overflow-hidden bg-[var(--surface-base)]">
        <div className="col-span-5 overflow-auto border-r border-[var(--border-faint)] bg-[var(--surface-container)]">
          <ResumePreview markdown={previewMarkdown} finalized={showFinalized} sessionId={sessionId} />
        </div>
        <div className={`overflow-hidden border-r border-[var(--border-faint)] ${copilotOpen ? "col-span-4" : "col-span-7"}`}>
          <SuggestionPanel />
        </div>
        {copilotOpen && (
          <div className="col-span-3 overflow-hidden min-h-0 bg-[var(--surface-container)]">
            <ChatPanel />
          </div>
        )}
      </div>
    </div>
  );
}

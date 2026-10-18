"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  BookOpen,
  Download,
  Loader2,
  MoreHorizontal,
  PanelRightClose,
  PanelRightOpen,
} from "lucide-react";
import ResumePreview from "@/components/edit/ResumePreview";
import SuggestionPanel from "@/components/edit/SuggestionPanel";
import ChatPanel from "@/components/edit/ChatPanel";
import CapacityMeter from "@/components/studio/CapacityMeter";
import { useAppStore, type DensityInfo } from "@/stores/useAppStore";
import { api } from "@/lib/api";
import { persistStudioMeta, getPersistedSessionId } from "@/lib/sessionBootstrap";
import { ROUTES } from "@/lib/navigation";
import { copy } from "@/lib/copy";
import { getClientId, loadLocalMemory } from "@/lib/userMemory";

export default function EditView() {
  const router = useRouter();
  const menuRef = useRef<HTMLDivElement>(null);
  const [buildingFromKb, setBuildingFromKb] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
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
    highlightSuggestionIds,
    jdAnalysis,
    matchResult,
    density,
    copilotOpen,
    setCopilotOpen,
    pushToast,
  } = useAppStore();

  useEffect(() => {
    if (!menuOpen) return;
    function onDocClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [menuOpen]);

  useEffect(() => {
    if (!sessionId) {
      // 有存档时先等水合，避免刷新被踢回准备页
      if (!getPersistedSessionId()) {
        router.replace(ROUTES.studioPrepare);
        return;
      }
      const timer = setTimeout(() => {
        if (!useAppStore.getState().sessionId) router.replace(ROUTES.studioPrepare);
      }, 1500);
      return () => clearTimeout(timer);
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
    setMenuOpen(false);
    const kb =
      knowledgeBase.trim() ||
      loadLocalMemory().knowledge_base_md.trim();
    if (!kb) {
      pushToast(copy.edit.kbEmpty, "warning");
      return;
    }
    if (!jdAnalysis) {
      pushToast(copy.prepare.needBoth, "warning");
      return;
    }
    setBuildingFromKb(true);
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
      pushToast(copy.edit.buildFromKbOk(d.suggestions_count), "success");
    } catch (e) {
      pushToast((e as Error).message || copy.edit.buildFromKbFail, "error");
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
    pushToast,
  ]);

  const previewHighlight = useMemo(() => {
    const id = highlightSuggestionIds[0];
    if (!id) return "";
    const sug = suggestions.find((s) => s.id === id);
    return sug?.original_text?.trim() || "";
  }, [highlightSuggestionIds, suggestions]);

  if (!sessionId) return null;

  const pending = suggestions.filter((s) => s.status === "pending" || s.status === "adjusted").length;
  const showFinalized = finalizeStatus === "finalized" && !!finalizedMarkdown;
  const previewMarkdown = showFinalized ? finalizedMarkdown : currentMarkdown;
  const contextTitle = jdAnalysis
    ? [jdAnalysis.company, jdAnalysis.role].filter(Boolean).join(" · ")
    : "";

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="toolbar">
        {contextTitle && (
          <span className="text-sm font-medium text-[var(--text-primary)] truncate max-w-[240px]">
            {contextTitle}
          </span>
        )}
        {matchResult && (
          <span className="chip-primary">{copy.edit.match(matchResult.overall_score)}</span>
        )}
        {pending > 0 && (
          <span className="chip">{copy.edit.pendingSuggestions(pending)}</span>
        )}
        <CapacityMeter
          sessionId={sessionId}
          markdown={currentMarkdown}
          onOpenExport={() => router.push(ROUTES.studioExport)}
        />
        <div className="ml-auto flex items-center gap-1.5">
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
            <Download size={14} /> {copy.edit.exportPdf}
          </button>
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              className="btn-secondary text-xs py-1.5 px-2"
              aria-label={copy.edit.moreActions}
              aria-expanded={menuOpen}
            >
              <MoreHorizontal size={16} />
            </button>
            {menuOpen && (
              <div className="absolute right-0 top-full mt-1 min-w-[11rem] rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--surface-container)] py-1 shadow-lg z-20">
                <button
                  type="button"
                  onClick={handleBuildFromKb}
                  disabled={buildingFromKb || !jdAnalysis}
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-left hover:bg-[var(--surface-base)] disabled:opacity-40"
                >
                  {buildingFromKb ? <Loader2 size={14} className="animate-spin" /> : <BookOpen size={14} />}
                  {buildingFromKb ? copy.edit.buildFromKbLoading : copy.edit.buildFromKb}
                </button>
                <Link
                  href={ROUTES.studioPrepare}
                  onClick={() => setMenuOpen(false)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-[var(--surface-base)]"
                >
                  <ArrowLeft size={14} /> {copy.edit.backPrepare}
                </Link>
                {density && (
                  <div className="px-3 py-2 text-xs text-[var(--text-secondary)] border-t border-[var(--border-faint)]">
                    {copy.edit.chars(density.char_count)}
                    {density.status === "sparse" && (
                      <span className="block mt-0.5 text-[var(--semantic-warning)]">{density.message}</span>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-12 min-h-0 overflow-hidden bg-[var(--surface-base)]">
        <div className="col-span-12 md:col-span-5 overflow-auto border-r border-[var(--border-faint)] bg-[var(--surface-container)]">
          <ResumePreview
            markdown={previewMarkdown}
            finalized={showFinalized}
            sessionId={sessionId}
            highlightText={previewHighlight}
          />
        </div>
        <div
          className={`col-span-12 md:overflow-hidden border-r border-[var(--border-faint)] min-h-0 ${
            copilotOpen ? "md:col-span-4" : "md:col-span-7"
          }`}
        >
          <SuggestionPanel />
        </div>
        {copilotOpen && (
          <div className="col-span-12 md:col-span-3 overflow-hidden min-h-0 bg-[var(--surface-container)] border-t md:border-t-0 border-[var(--border-faint)]">
            <ChatPanel />
          </div>
        )}
      </div>
    </div>
  );
}

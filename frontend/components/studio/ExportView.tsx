"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Download, FileText, Loader2, CheckCircle2, Undo2 } from "lucide-react";
import ResumePreview from "@/components/edit/ResumePreview";
import ProfilePhotoModule from "@/components/upload/ProfilePhotoModule";
import { useAppStore } from "@/stores/useAppStore";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import { persistStudioMeta } from "@/lib/sessionBootstrap";
import { ROUTES } from "@/lib/navigation";
import { copy } from "@/lib/copy";

export default function ExportView() {
  const router = useRouter();
  const {
    sessionId,
    parsedResume,
    jdAnalysis,
    jdText,
    suggestions,
    currentMarkdown,
    finalizedMarkdown,
    finalizeStatus,
    setFinalizedMarkdown,
    setFinalizeStatus,
    pushToast,
  } = useAppStore();
  const [mode, setMode] = useState<"standard" | "diff">("standard");
  const [busy, setBusy] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [error, setError] = useState("");
  const [appId, setAppId] = useState("");
  const [unfinalizing, setUnfinalizing] = useState(false);
  const [layoutCheck, setLayoutCheck] = useState<{
    ok: boolean;
    bottom_gap_mm?: number | null;
    char_count?: number;
    density_message?: string;
    layout_issues?: string[];
  } | null>(null);
  const [layoutLoading, setLayoutLoading] = useState(false);
  const [emphasisPhrases, setEmphasisPhrases] = useState<string[]>([]);

  const isFinalized = finalizeStatus === "finalized" && !!finalizedMarkdown;

  useEffect(() => {
    if (!sessionId) {
      router.replace(ROUTES.studioPrepare);
      return;
    }
    persistStudioMeta({
      sessionId,
      step: 3,
      company: jdAnalysis?.company,
      role: jdAnalysis?.role,
    });
  }, [sessionId, router, jdAnalysis?.company, jdAnalysis?.role]);

  useEffect(() => {
    if (!sessionId || !isFinalized) {
      setLayoutCheck(null);
      return;
    }
    setLayoutLoading(true);
    api
      .exportLayoutCheck(sessionId)
      .then((res) => {
        if (res.success && res.data) setLayoutCheck(res.data);
      })
      .catch(() => setLayoutCheck(null))
      .finally(() => setLayoutLoading(false));
  }, [sessionId, isFinalized, finalizedMarkdown]);

  if (!sessionId) return null;

  const previewMd = isFinalized ? finalizedMarkdown : currentMarkdown;
  const pending = suggestions.filter((s) => s.status === "pending" || s.status === "adjusted").length;

  const filename = `${jdAnalysis?.company || "目标公司"}+${parsedResume?.header.name || "候选人"}+${
    jdAnalysis?.role || "目标岗位"
  }.pdf`;

  async function onFinalize() {
    if (pending > 0) {
      setError(copy.export.pendingBlock(pending));
      return;
    }
    setFinalizing(true);
    setError("");
    try {
      const res = await api.finalizeResume(sessionId);
      if (!res.success || !res.data) throw new Error("定稿失败");
      setFinalizedMarkdown(res.data.markdown);
      setFinalizeStatus("finalized");
      setEmphasisPhrases(res.data.emphasis_phrases || []);
      const v = res.data.validation;
      const emphasis = res.data.emphasis_phrases || [];
      if (v?.layout_issues?.length) {
        pushToast(v.layout_issues.join("；"), "warning", 10000);
      } else if (emphasis.length > 0) {
        pushToast(copy.export.finalizeEmphasis(emphasis.length), "success");
      } else if (v?.bottom_gap_mm != null) {
        pushToast(`${copy.export.finalizeOk}，${copy.export.bottomGap(v.bottom_gap_mm)}`, "success");
      } else {
        pushToast(copy.export.finalizeOk, "success");
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setFinalizing(false);
    }
  }

  async function onUnfinalize() {
    setUnfinalizing(true);
    setError("");
    try {
      const res = await api.unfinalizeResume(sessionId);
      if (!res.success) throw new Error(res.error || "撤销定稿失败");
      setFinalizeStatus("draft");
      pushToast(copy.export.unfinalizeOk, "success");
      router.push(ROUTES.studioEdit);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUnfinalizing(false);
    }
  }

  async function download() {
    if (!isFinalized) {
      setError(copy.export.finalizeNeedFirst);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const blob = await api.exportPdf(sessionId, mode);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      pushToast(copy.edit.pdfDownloading, "success");

      api.hub.recordFunnel(getClientId(), "export_pdf", { session_id: sessionId }).catch(() => {});

      try {
        const ats = await api.hub.atsReadback(sessionId, filename);
        if (ats.success && ats.data) {
          const score = ats.data.ats_score;
          if (ats.data.readable) {
            pushToast(`ATS 可读性 ${score} 分，机器可较好解析`, "success");
          } else {
            pushToast(`ATS 可读性偏低（${score} 分）：${ats.data.issues[0] || "请检查排版"}`, "warning");
          }
        }
      } catch {
        /* PDF 可能尚未落盘到服务端路径，忽略 */
      }

      if (jdAnalysis) {
        const created = await api.createApplication({
          client_id: getClientId(),
          company: jdAnalysis.company || "未命名公司",
          role: jdAnalysis.role,
          jd_text: jdText,
          match_score: 0,
          decision_level: "moderate",
          session_id: sessionId,
          status: "Applied",
        });
        if (created.success && created.data?.id) {
          setAppId(created.data.id);
          pushToast(copy.export.tracked, "success");
        }
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const accepted = suggestions.filter((s) => s.status === "accepted").length;

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-5xl mx-auto px-4 md:px-6 py-6 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="page-title">{copy.export.title}</h1>
          <div className="flex flex-wrap items-center gap-2">
            <Link href={ROUTES.studioEdit} className="btn-secondary">
              <ArrowLeft size={14} /> {copy.export.backEdit}
            </Link>
            {isFinalized && (
              <button
                type="button"
                onClick={onUnfinalize}
                disabled={unfinalizing}
                className="btn-secondary text-[var(--semantic-warning)] border-[var(--semantic-warning)]/30"
              >
                {unfinalizing ? <Loader2 size={14} className="animate-spin" /> : <Undo2 size={14} />}
                {copy.export.unfinalize}
              </button>
            )}
          </div>
        </div>

        {!isFinalized && (
          <div className="alert-warning">
            <p className="mb-4">{copy.export.finalizeHint(pending)}</p>
            <button
              type="button"
              onClick={onFinalize}
              disabled={finalizing || pending > 0}
              className="btn-primary"
              style={{ background: "var(--semantic-success)" }}
            >
              {finalizing ? <Loader2 size={14} className="animate-spin" /> : null}
              {copy.export.finalize}
            </button>
          </div>
        )}

        {isFinalized && (
          <div
            className={`section-card text-sm ${
              layoutCheck?.ok
                ? "border-[var(--semantic-success)]/20"
                : "border-[var(--semantic-warning)]/30"
            }`}
          >
          {layoutLoading ? (
            <span className="inline-flex items-center gap-2 text-[var(--text-secondary)]">
              <Loader2 size={14} className="animate-spin" /> {copy.export.layoutChecking}
            </span>
          ) : layoutCheck ? (
            <div className="space-y-1">
              <p>
                {layoutCheck.ok ? copy.export.layoutOk : copy.export.layoutWarn}
                {layoutCheck.bottom_gap_mm != null && (
                  <span className="ml-2">
                    {copy.export.bottomGap(layoutCheck.bottom_gap_mm)}
                   {layoutCheck.bottom_gap_mm > 20 ? copy.export.bottomGapLarge : copy.export.bottomGapOk}
                  </span>
                )}
                {layoutCheck.char_count != null && (
                  <span className="ml-2 text-[var(--text-secondary)]">
                    · 约 {layoutCheck.char_count} 字
                  </span>
                )}
              </p>
              {layoutCheck.density_message && (
                <p className="text-xs text-[var(--text-secondary)]">{layoutCheck.density_message}</p>
              )}
              {emphasisPhrases.length > 0 && (
                <p className="text-xs text-[var(--text-secondary)]">
                  {copy.export.emphasis(emphasisPhrases, emphasisPhrases.length)}
                </p>
              )}
              {layoutCheck.layout_issues && layoutCheck.layout_issues.length > 0 && (
                <ul className="text-xs list-disc pl-4 text-[var(--semantic-warning)]">
                  {layoutCheck.layout_issues.map((issue) => (
                    <li key={issue}>{issue}</li>
                  ))}
                </ul>
              )}
            </div>
          ) : null}
        </div>
      )}

      <ProfilePhotoModule sessionId={sessionId} />

      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="text-sm text-[var(--text-secondary)]">
          {copy.export.accepted(accepted)}
          {isFinalized && (
            <span className="ml-2 text-[var(--semantic-success)] inline-flex items-center gap-1">
              <CheckCircle2 size={14} /> {copy.export.finalized}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={download}
          disabled={busy || !isFinalized}
          className="btn-primary"
        >
          {busy ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
          {copy.export.download}
        </button>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 section-card overflow-hidden p-0">
          <ResumePreview markdown={previewMd} finalized={isFinalized} sessionId={sessionId} />
        </div>
        <div className="space-y-3">
          <ModeCard active={mode === "standard"} onClick={() => setMode("standard")} title={copy.export.standard} desc={copy.export.standardDesc} />
          <ModeCard active={mode === "diff"} onClick={() => setMode("diff")} title={copy.export.diff} desc={copy.export.diffDesc} />
          {appId && (
            <Link href={`/interview/${appId}`} className="text-link block px-1">
              {copy.export.interviewPrep} →
            </Link>
          )}
        </div>
      </div>

      {error && <p className="alert-error">{error}</p>}
      </div>
    </div>
  );
}

function ModeCard({
  active,
  onClick,
  title,
  desc,
}: {
  active: boolean;
  onClick: () => void;
  title: string;
  desc: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`section-card p-4 text-left w-full text-sm transition-colors ${
        active ? "border-[var(--primary)] bg-[var(--primary-muted)]" : "hover:border-[var(--primary)]/40"
      }`}
    >
      <div className="font-medium flex items-center gap-2">
        <FileText size={14} /> {title}
      </div>
      <div className="text-[var(--text-secondary)] mt-1">{desc}</div>
    </button>
  );
}

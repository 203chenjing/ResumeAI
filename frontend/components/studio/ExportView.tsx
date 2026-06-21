"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Download, FileText, Loader2, CheckCircle2 } from "lucide-react";
import ResumePreview from "@/components/edit/ResumePreview";
import ProfilePhotoModule from "@/components/upload/ProfilePhotoModule";
import { useAppStore } from "@/stores/useAppStore";
import { api } from "@/lib/api";
import { getClientId } from "@/lib/userMemory";
import { persistStudioMeta } from "@/lib/sessionBootstrap";
import { ROUTES } from "@/lib/navigation";

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

  if (!sessionId) return null;

  const isFinalized = finalizeStatus === "finalized" && !!finalizedMarkdown;
  const previewMd = isFinalized ? finalizedMarkdown : currentMarkdown;
  const pending = suggestions.filter((s) => s.status === "pending" || s.status === "adjusted").length;

  const filename = `${jdAnalysis?.company || "目标公司"}+${parsedResume?.header.name || "候选人"}+${
    jdAnalysis?.role || "目标岗位"
  }.pdf`;

  async function onFinalize() {
    if (pending > 0) {
      setError(`还有 ${pending} 条建议未处理`);
      return;
    }
    setFinalizing(true);
    setError("");
    try {
      const res = await api.finalizeResume(sessionId);
      if (!res.success || !res.data) throw new Error("定稿失败");
      setFinalizedMarkdown(res.data.markdown);
      setFinalizeStatus("finalized");
      pushToast("定稿成功", "success");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setFinalizing(false);
    }
  }

  async function download() {
    if (!isFinalized) {
      setError("请先确认定稿");
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
      pushToast("PDF 下载已开始", "success");

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
          pushToast("已记入投递追踪", "success");
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
    <div className="h-full overflow-auto p-4 md:p-6 max-w-6xl mx-auto">
      <h1 className="text-lg font-semibold mb-4">导出 PDF</h1>

      {!isFinalized && (
        <div className="mb-4 p-4 rounded-xl border border-amber-200 bg-amber-50">
          <p className="text-sm text-amber-900 mb-3">
            定稿后预览将与导出 PDF 完全一致。{pending > 0 ? `还有 ${pending} 条建议未处理。` : ""}
          </p>
          <button
            type="button"
            onClick={onFinalize}
            disabled={finalizing || pending > 0}
            className="px-4 py-2 bg-[var(--semantic-success)] text-white rounded-lg text-sm disabled:opacity-40"
          >
            {finalizing ? <Loader2 size={14} className="animate-spin inline" /> : null} 确认定稿
          </button>
        </div>
      )}

      <div className="mb-4">
        <ProfilePhotoModule sessionId={sessionId} />
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
        <div className="text-sm text-[var(--text-secondary)]">
          已接受 {accepted} 条建议
          {isFinalized && (
            <span className="ml-2 text-[var(--semantic-success)] inline-flex items-center gap-1">
              <CheckCircle2 size={14} /> 已定稿
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={download}
          disabled={busy || !isFinalized}
          className="inline-flex items-center gap-2 px-6 py-2.5 bg-[var(--primary)] text-white rounded-lg disabled:opacity-40"
        >
          {busy ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
          下载 PDF
        </button>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 border border-[var(--border-subtle)] rounded-xl overflow-hidden">
          <ResumePreview markdown={previewMd} finalized={isFinalized} sessionId={sessionId} />
        </div>
        <div className="space-y-3">
          <ModeCard active={mode === "standard"} onClick={() => setMode("standard")} title="标准版" desc="干净最终版" />
          <ModeCard active={mode === "diff"} onClick={() => setMode("diff")} title="修改痕迹版" desc="保留 diff 标记" />
          {appId && (
            <Link href={`/interview/${appId}`} className="block text-sm text-[var(--primary)] hover:underline">
              面试准备 →
            </Link>
          )}
        </div>
      </div>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
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
      className={`p-4 text-left rounded-xl border w-full text-sm ${
        active ? "border-[var(--primary)] bg-[var(--primary-muted)]" : "border-[var(--border-subtle)]"
      }`}
    >
      <div className="font-medium flex items-center gap-2">
        <FileText size={14} /> {title}
      </div>
      <div className="text-[var(--text-secondary)] mt-1">{desc}</div>
    </button>
  );
}

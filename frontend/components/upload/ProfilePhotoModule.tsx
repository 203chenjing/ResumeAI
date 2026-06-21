"use client";

import { useEffect, useState } from "react";
import { Camera, Trash2, Upload, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAppStore, type FinalizeStatus } from "@/stores/useAppStore";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ProfilePhotoModule({ sessionId }: { sessionId: string }) {
  const { setCurrentMarkdown, setFinalizeStatus, pushToast } = useAppStore();
  const [hasPhoto, setHasPhoto] = useState(false);
  const [busy, setBusy] = useState(false);
  const [previewUrl, setPreviewUrl] = useState("");

  useEffect(() => {
    if (!sessionId) return;
    api.getKnowledgeBase(sessionId).then((res) => {
      if (res.success && res.data?.has_photo) {
        setHasPhoto(true);
        setPreviewUrl(`${API_BASE}/api/knowledge-base/photo/${sessionId}?t=${Date.now()}`);
      }
    }).catch(() => {});
  }, [sessionId]);

  async function onUpload(file: File) {
    if (!sessionId) {
      pushToast("请先上传简历", "warning");
      return;
    }
    setBusy(true);
    try {
      const res = await api.uploadProfilePhoto(sessionId, file);
      if (!res.success || !res.data) throw new Error("上传失败");
      setHasPhoto(true);
      setPreviewUrl(`${API_BASE}/api/knowledge-base/photo/${sessionId}?t=${Date.now()}`);
      if (res.data.current_markdown) setCurrentMarkdown(res.data.current_markdown);
      if (res.data.finalize_status) setFinalizeStatus(res.data.finalize_status as FinalizeStatus);
      pushToast("照片已裁剪并写入简历", "success");
    } catch (e) {
      pushToast((e as Error).message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function onRemove() {
    if (!sessionId) return;
    setBusy(true);
    try {
      const res = await api.deleteProfilePhoto(sessionId);
      if (res.success && res.data?.current_markdown) {
        setCurrentMarkdown(res.data.current_markdown);
      }
      setHasPhoto(false);
      setPreviewUrl("");
      pushToast("已移除个人照片", "info");
    } catch (e) {
      pushToast((e as Error).message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mb-4 p-4 bg-slate-50 border border-slate-200 rounded-lg">
      <div className="flex items-start gap-4">
        <div className="w-20 h-[118px] flex-shrink-0 bg-white border border-dashed border-slate-300 rounded-lg overflow-hidden flex items-center justify-center">
          {previewUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={previewUrl} alt="个人照片预览" className="w-full h-full object-cover" />
          ) : (
            <Camera className="text-slate-300" size={28} />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm text-slate-800 mb-1">个人照片（自定义模块）</div>
          <p className="text-xs text-slate-500 mb-3 leading-relaxed">
            上传后会自动裁剪为 540×790 比例，写入简历并在 PDF 右上角显示。属于每人专属配置，随知识库一并保存。
          </p>
          <div className="flex flex-wrap gap-2">
            <label
              className={`inline-flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg cursor-pointer ${
                busy || !sessionId
                  ? "bg-slate-200 text-slate-400 cursor-not-allowed"
                  : "bg-blue-600 text-white hover:bg-blue-700"
              }`}
            >
              {busy ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
              上传照片
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                disabled={busy || !sessionId}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) onUpload(f);
                  e.target.value = "";
                }}
              />
            </label>
            {hasPhoto && (
              <button
                type="button"
                disabled={busy}
                onClick={onRemove}
                className="inline-flex items-center gap-1 px-3 py-1.5 text-sm bg-white border border-slate-300 rounded-lg hover:bg-slate-100 disabled:opacity-50"
              >
                <Trash2 size={14} /> 移除
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

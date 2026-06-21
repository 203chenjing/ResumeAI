"use client";

import { useEffect, useState } from "react";
import { Camera, Trash2, Upload, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAppStore, type FinalizeStatus } from "@/stores/useAppStore";
import { copy } from "@/lib/copy";

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
      pushToast(copy.photo.needResume, "warning");
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
      pushToast(copy.photo.uploadOk, "success");
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
      pushToast(copy.photo.removeOk, "info");
    } catch (e) {
      pushToast((e as Error).message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mb-4 p-4 surface-card">
      <div className="flex items-start gap-4">
        <div className="w-20 h-[118px] flex-shrink-0 bg-[var(--surface-base)] border border-dashed border-[var(--border-subtle)] rounded-lg overflow-hidden flex items-center justify-center">
          {previewUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={previewUrl} alt="个人照片预览" className="w-full h-full object-cover" />
          ) : (
            <Camera className="text-[var(--text-disabled)]" size={28} />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm text-[var(--text-primary)] mb-1">{copy.photo.title}</div>
          <p className="text-xs text-[var(--text-secondary)] mb-3 leading-relaxed">{copy.photo.hint}</p>
          <div className="flex flex-wrap gap-2">
            <label
              className={`inline-flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg cursor-pointer ${
                busy || !sessionId
                  ? "bg-[var(--surface-base)] text-[var(--text-disabled)] cursor-not-allowed"
                  : "btn-primary"
              }`}
            >
              {busy ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
              {copy.photo.upload}
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
                className="btn-secondary"
              >
                <Trash2 size={14} /> {copy.photo.remove}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { useEffect } from "react";
import { prepareResumePreviewMarkdown, stripPhotoMarkdown } from "@/lib/resumePreviewTransform";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function markdownForPreview(md: string, sessionId?: string) {
  let text = md;
  if (sessionId) {
    const photoUrl = `${API_BASE}/api/knowledge-base/photo/${sessionId}`;
    text = text.replace(
      /!\[个人照片\]\([^)]+\)/,
      `![个人照片](${photoUrl})`
    );
  }
  const { md: withoutPhoto, hadPhoto } = stripPhotoMarkdown(text);
  const transformed = prepareResumePreviewMarkdown(withoutPhoto);
  return { displayMd: transformed, hadPhoto: hadPhoto || /!\[个人照片\]/.test(md) };
}

export function injectResumeHighlight(md: string, snippet: string | undefined): string {
  const needle = snippet?.trim();
  if (!needle || needle.length < 8 || !md.includes(needle)) return md;
  return md.split(needle).join(`<mark class="resume-highlight">${needle}</mark>`);
}

export default function ResumePreview({
  markdown,
  finalized = false,
  sessionId,
  highlightText,
}: {
  markdown: string;
  finalized?: boolean;
  sessionId?: string;
  highlightText?: string;
}) {
  const { displayMd, hadPhoto } = markdownForPreview(markdown, sessionId);
  const highlightedBody = injectResumeHighlight(
    hadPhoto && sessionId
      ? displayMd.split(/(?=## )/).slice(1).join("## ").replace(/^/, "## ")
      : displayMd,
    highlightText
  );
  const headerMd = displayMd.split(/(?=## )/)[0].trim();
  const bodyMd =
    hadPhoto && sessionId
      ? highlightedBody
      : injectResumeHighlight(displayMd, highlightText);
  const photoUrl = sessionId ? `${API_BASE}/api/knowledge-base/photo/${sessionId}` : "";

  useEffect(() => {
    if (!highlightText?.trim()) return;
    const el = document.querySelector(".resume-highlight");
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlightText, markdown]);

  return (
    <div className="bg-white">
      <div
        className={`px-6 py-2 text-xs border-b ${
          finalized
            ? "bg-green-50 text-green-800 border-green-200"
            : "bg-amber-50 text-amber-800 border-amber-200"
        }`}
      >
        {finalized
          ? "定稿预览 · 此内容与导出 PDF 完全一致（A4 单页）"
          : hadPhoto
            ? "工作稿预览 · 照片右上角 58×85pt，不遮挡正文"
            : "工作稿预览 · 可在导出页上传照片，定稿后导出"}
      </div>
      <div
        className={`markdown-body prose prose-sm max-w-none p-6 min-h-[200px] resume-preview-a4 relative${
          hadPhoto ? " resume-preview-a4--with-photo" : ""
        }`}
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
          {headerMd}
        </ReactMarkdown>
        {hadPhoto && sessionId && (
          <p className="photo">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={photoUrl} alt="个人照片" />
          </p>
        )}
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
          {bodyMd}
        </ReactMarkdown>
      </div>
      <style jsx global>{`
        .resume-preview-a4 {
          position: relative;
          font-size: 9.5pt;
          line-height: 1.3;
        }
        .resume-preview-a4 h1 {
          text-align: center;
          font-size: 17pt;
          margin: 0 0 3pt;
        }
        .resume-preview-a4 .contact-line,
        .resume-preview-a4 .target-role {
          text-align: center;
          font-size: 10pt;
          margin: 0;
        }
        .resume-preview-a4 .target-role {
          font-weight: 700;
        }
        .resume-preview-a4 .photo {
          position: absolute;
          top: 1.5rem;
          right: 1.5rem;
          margin: 0;
          width: 58pt;
          height: 85pt;
        }
        .resume-preview-a4 .photo img {
          display: block;
          width: 58pt;
          height: 85pt;
          object-fit: contain;
          object-position: center;
          background: #fff;
        }
        .resume-preview-a4--with-photo .resume-header-row {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto auto;
          column-gap: 10pt;
          width: calc(100% - 64pt);
          max-width: calc(100% - 64pt);
          font-size: 10.5pt;
          font-weight: 700;
          margin: 0 0 2pt;
          align-items: baseline;
        }
        .resume-preview-a4--with-photo .resume-header-row > span {
          display: block;
        }
        .resume-preview-a4--with-photo .resume-header-row .col-left {
          white-space: nowrap;
          text-align: left;
        }
        .resume-preview-a4 .resume-header-row {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto auto;
          column-gap: 10pt;
          width: 100%;
          font-size: 10.5pt;
          font-weight: 700;
          margin: 0 0 2pt;
          align-items: baseline;
        }
        .resume-preview-a4 .resume-header-row > span {
          display: block;
        }
        .resume-preview-a4 .resume-header-row .col-left {
          text-align: left;
          white-space: nowrap;
        }
        .resume-preview-a4 .resume-header-row .col-mid,
        .resume-preview-a4 .resume-header-row .col-right {
          text-align: right;
          white-space: nowrap;
        }
        .resume-preview-a4 .resume-header-row .col-right {
          min-width: 5.5em;
        }
        .resume-preview-a4 mark.resume-highlight {
          background: #fef7e0;
          color: #b45309;
          padding: 0 2px;
          border-radius: 2px;
        }
      `}</style>
    </div>
  );
}

"use client";

import { useState } from "react";
import { getLinkPreviewMeta, type LinkPreviewMeta } from "@/lib/linkPreview";

type TrainingResourcePreviewProps = {
  url: string;
  title?: string;
  compact?: boolean;
};

function PreviewMedia({ meta, title }: { meta: LinkPreviewMeta; title?: string }) {
  const [imgFailed, setImgFailed] = useState(false);

  if (meta.thumbnailUrl && !imgFailed) {
    return (
      <div className="relative aspect-video w-full overflow-hidden bg-brand-100">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={meta.thumbnailUrl}
          alt={title ? `Preview for ${title}` : "Resource preview"}
          className="h-full w-full object-cover"
          loading="lazy"
          onError={() => setImgFailed(true)}
        />
        {meta.kind === "youtube" && (
          <span className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-black/70 text-white shadow-lg">
              <svg viewBox="0 0 24 24" className="ml-0.5 h-5 w-5 fill-current" aria-hidden>
                <path d="M8 5v14l11-7z" />
              </svg>
            </span>
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="relative flex aspect-video w-full flex-col items-center justify-center gap-3 bg-gradient-to-br from-brand-50 via-white to-brand-100 px-4">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={meta.faviconUrl}
        alt=""
        width={40}
        height={40}
        className="h-10 w-10 rounded-lg border border-brand-200 bg-white p-1.5 shadow-sm"
        loading="lazy"
      />
      <p className="max-w-full truncate text-center text-sm font-medium text-brand-900">
        {meta.hostname}
      </p>
      <p className="max-w-full truncate text-center text-xs text-brand-300">{meta.label}</p>
    </div>
  );
}

export function TrainingResourcePreview({
  url,
  title,
  compact = false,
}: TrainingResourcePreviewProps) {
  const meta = getLinkPreviewMeta(url);
  if (!meta) return null;

  return (
    <a
      href={meta.href}
      target="_blank"
      rel="noopener noreferrer"
      className={`group block overflow-hidden rounded-xl border border-brand-200 bg-white transition hover:border-brand-400 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600/40 ${
        compact ? "max-w-sm" : ""
      }`}
    >
      <PreviewMedia meta={meta} title={title} />
      <div className="flex items-center justify-between gap-3 border-t border-brand-100 px-3 py-2.5">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium uppercase tracking-wide text-brand-300">
            {meta.kind === "youtube"
              ? "YouTube"
              : meta.kind === "vimeo"
                ? "Vimeo"
                : "Learning resource"}
          </p>
          <p className="truncate text-sm text-brand-900 group-hover:text-brand-700">
            {meta.hostname}
          </p>
        </div>
        <span className="shrink-0 rounded-lg bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-800 group-hover:bg-brand-100">
          Open
        </span>
      </div>
    </a>
  );
}

/** Live preview while typing a URL (create/edit forms). */
export function TrainingResourcePreviewLive({ url }: { url: string }) {
  const meta = getLinkPreviewMeta(url);
  if (!meta) {
    if (!url.trim()) return null;
    return (
      <p className="text-xs text-brand-300">
        Enter a valid http(s) URL to see a preview (YouTube links show a thumbnail).
      </p>
    );
  }
  return <TrainingResourcePreview url={url} compact />;
}

"use client";

import type { KnowledgeCitation } from "@/types/ai";

export function AICitationList({ citations }: { citations: KnowledgeCitation[] }) {
  if (!citations.length) return null;

  return (
    <div className="mt-4 rounded-2xl border border-brand-200/80 bg-brand-50/60 px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-brand-600 mb-2">
        Sources
      </p>
      <ul className="space-y-2">
        {citations.map((citation) => (
          <li key={citation.citation_id} className="flex gap-3 text-sm">
            <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-md bg-brand-600 text-[11px] font-semibold text-white">
              {citation.citation_id}
            </span>
            <div className="min-w-0">
              <p className="font-medium text-brand-900 truncate">
                {citation.document_name || `Document ${citation.company_document_id}`}
              </p>
              <p className="text-xs text-brand-300">
                Page{" "}
                {citation.page_start === citation.page_end
                  ? citation.page_start
                  : `${citation.page_start}–${citation.page_end}`}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

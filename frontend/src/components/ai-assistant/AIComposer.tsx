"use client";

import { useRef, type FormEvent, type KeyboardEvent } from "react";
import { useAIAssistant } from "@/hooks/useAIAssistant";

export function AIComposer() {
  const { draft, setDraft, ask, loading, clearError } = useAIAssistant();
  const areaRef = useRef<HTMLTextAreaElement>(null);

  const onSubmit = async (event?: FormEvent) => {
    event?.preventDefault();
    clearError();
    await ask();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void onSubmit();
    }
  };

  return (
    <form
      onSubmit={onSubmit}
      className="w-full max-w-2xl mx-auto rounded-3xl border border-brand-200 bg-white shadow-[0_18px_50px_-28px_rgba(15,34,74,0.35)]"
    >
      <label htmlFor="ai-composer-input" className="sr-only">
        Ask about company knowledge
      </label>
      <div className="flex items-start gap-3 px-5 pt-4">
        <span
          className="mt-1.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600 text-sm"
          aria-hidden
        >
          ✦
        </span>
        <textarea
          id="ai-composer-input"
          ref={areaRef}
          rows={3}
          value={draft}
          disabled={loading}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask about company policies, procedures, documents…"
          className="w-full resize-none border-0 bg-transparent text-sm sm:text-base text-brand-900 placeholder:text-brand-300 focus:outline-none focus:ring-0 disabled:opacity-60"
        />
      </div>
      <div className="flex items-center justify-between gap-3 px-4 pb-4 pt-2">
        <p className="text-xs text-brand-300 pl-1">
          Answers use your company document library
        </p>
        <button
          type="submit"
          disabled={loading || !draft.trim()}
          aria-label="Send question"
          className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand-600 text-white shadow-md transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-brand-200 disabled:text-brand-50"
        >
          <svg
            viewBox="0 0 24 24"
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            aria-hidden
          >
            <path d="M12 19V5M5 12l7-7 7 7" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </form>
  );
}

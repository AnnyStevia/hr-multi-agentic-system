"use client";

import { useAIAssistant } from "@/hooks/useAIAssistant";
import { AIAssistantWelcome } from "./AIAssistantWelcome";
import { AIComposer } from "./AIComposer";
import { AIConversation } from "./AIConversation";

export function AIAssistantPanel() {
  const {
    hasConversation,
    error,
    clearError,
    setDraft,
    ask,
    loading,
  } = useAIAssistant();

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div
        className={
          hasConversation
            ? "flex-1 min-h-0 overflow-y-auto"
            : "flex-1 min-h-0 overflow-hidden"
        }
      >
        {hasConversation ? (
          <AIConversation />
        ) : (
          <AIAssistantWelcome
            onPickSuggestion={(text) => {
              setDraft(text);
              void ask(text);
            }}
          />
        )}
      </div>

      <div className="shrink-0 border-t border-brand-200/70 bg-white/90 px-4 sm:px-6 py-4 backdrop-blur-sm">
        {error ? (
          <div
            role="alert"
            className="mb-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 flex items-start justify-between gap-3"
          >
            <p>{error}</p>
            <button
              type="button"
              onClick={clearError}
              className="shrink-0 text-xs font-medium underline"
            >
              Dismiss
            </button>
          </div>
        ) : null}
        <AIComposer />
        {loading && !hasConversation ? (
          <p className="mt-2 text-center text-xs text-brand-300">Thinking…</p>
        ) : null}
      </div>
    </div>
  );
}

"use client";

import type { AIChatMessage } from "@/types/ai";
import { useAIAssistant } from "@/hooks/useAIAssistant";
import { AICitationList } from "./AICitationList";

function renderAnswer(content: string) {
  const parts = content.split(/(\[\d+\])/g);
  return parts.map((part, index) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (match) {
      return (
        <span
          key={`${part}-${index}`}
          className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded bg-brand-100 px-1 text-[11px] font-semibold text-brand-700 align-middle"
        >
          {match[1]}
        </span>
      );
    }
    return <span key={`${part}-${index}`}>{part}</span>;
  });
}

export function AIMessage({ message }: { message: AIChatMessage }) {
  const isUser = message.role === "user";
  const { confirmPending, cancelPending, loading } = useAIAssistant();
  const pending = message.pendingConfirmation;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[min(100%,42rem)] rounded-2xl px-4 py-3 text-sm sm:text-base leading-relaxed ${
          isUser
            ? "bg-brand-600 text-white shadow-sm"
            : "bg-white border border-brand-200 text-brand-900 shadow-sm"
        }`}
      >
        <div className="whitespace-pre-wrap">
          {isUser ? message.content : renderAnswer(message.content)}
        </div>
        {!isUser && pending ? (
          <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-brand-900">
            <p className="font-medium text-amber-900">Confirmation required</p>
            <p className="mt-1 whitespace-pre-wrap text-brand-800">{pending.summary}</p>
            <p className="mt-1 text-xs text-brand-600">
              Tool: {pending.tool_name}. No changes applied yet.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={loading}
                onClick={() => void confirmPending(message.id)}
                className="rounded-lg bg-brand-700 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60"
              >
                Confirm
              </button>
              <button
                type="button"
                disabled={loading}
                onClick={() => cancelPending(message.id)}
                className="rounded-lg border border-brand-300 bg-white px-3 py-1.5 text-sm font-medium text-brand-800 disabled:opacity-60"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : null}
        {!isUser && message.confirmationResolved === "confirmed" ? (
          <p className="mt-2 text-xs font-medium text-emerald-700">Action confirmed.</p>
        ) : null}
        {!isUser && message.citations ? (
          <AICitationList citations={message.citations} />
        ) : null}
      </div>
    </div>
  );
}

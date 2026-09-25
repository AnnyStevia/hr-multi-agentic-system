"use client";

import type { AIChatMessage } from "@/types/ai";
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
        {!isUser && message.citations ? (
          <AICitationList citations={message.citations} />
        ) : null}
      </div>
    </div>
  );
}

"use client";

import { useEffect, useRef } from "react";
import { useAIAssistant } from "@/hooks/useAIAssistant";
import { AILoadingState } from "./AILoadingState";
import { AIMessage } from "./AIMessage";

export function AIConversation() {
  const { messages, loading } = useAIAssistant();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-8 py-6 space-y-4">
      {messages.map((message) => (
        <AIMessage key={message.id} message={message} />
      ))}
      {loading ? <AILoadingState /> : null}
      <div ref={endRef} />
    </div>
  );
}

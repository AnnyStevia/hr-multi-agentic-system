"use client";

import Image from "next/image";
import { useAIAssistant } from "@/hooks/useAIAssistant";
import type { AIAssistantAgentMode } from "@/types/ai";

const LOADING: Record<AIAssistantAgentMode, string> = {
  knowledge: "Consulting company knowledge…",
  recruitment: "Consulting recruitment data…",
  leave: "Consulting leave data…",
};

export function AILoadingState() {
  const { agentMode } = useAIAssistant();

  return (
    <div className="flex justify-start animate-dash-fade-in px-4 sm:px-8">
      <div className="inline-flex items-center gap-3 rounded-2xl border border-brand-200 bg-white px-4 py-3 shadow-sm">
        <Image
          src="/ai/assistant-orb.png"
          alt=""
          width={28}
          height={28}
          className="animate-dash-pulse-soft"
        />
        <div className="flex items-center gap-1.5 h-4" aria-label="Thinking">
          <span className="h-1.5 w-1.5 rounded-full bg-brand-500 animate-ai-dot-bounce" />
          <span
            className="h-1.5 w-1.5 rounded-full bg-brand-500 animate-ai-dot-bounce"
            style={{ animationDelay: "0.16s" }}
          />
          <span
            className="h-1.5 w-1.5 rounded-full bg-brand-500 animate-ai-dot-bounce"
            style={{ animationDelay: "0.32s" }}
          />
        </div>
        <span className="text-sm text-brand-300">{LOADING[agentMode]}</span>
      </div>
    </div>
  );
}

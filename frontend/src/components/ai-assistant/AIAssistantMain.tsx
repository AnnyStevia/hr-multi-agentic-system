"use client";

import type { ReactNode } from "react";
import { useAIAssistant } from "@/hooks/useAIAssistant";
import { AIAssistantPanel } from "./AIAssistantPanel";

type AIAssistantMainProps = {
  children: ReactNode;
  /** Classes applied to the route content container when the assistant is closed. */
  contentClassName?: string;
};

export function AIAssistantMain({
  children,
  contentClassName = "flex-1 min-h-0 overflow-y-auto p-6",
}: AIAssistantMainProps) {
  const { open } = useAIAssistant();

  return (
    <>
      <div className={open ? "hidden" : contentClassName} aria-hidden={open}>
        {children}
      </div>
      {open ? (
        <div className="relative flex-1 min-h-0 h-full flex flex-col overflow-hidden ai-panel-surface animate-ai-panel-enter">
          <div className="pointer-events-none absolute inset-0 ai-panel-glow-burst" aria-hidden />
          <div className="relative flex-1 min-h-0 flex flex-col overflow-hidden">
            <AIAssistantPanel />
          </div>
        </div>
      ) : null}
    </>
  );
}

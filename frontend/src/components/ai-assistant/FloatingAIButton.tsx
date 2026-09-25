"use client";

import Image from "next/image";
import { useAIAssistant } from "@/hooks/useAIAssistant";
import { useDraggableAI } from "@/hooks/useDraggableAI";

export function FloatingAIButton() {
  const { open, openAssistant, closeAssistant } = useAIAssistant();
  const { position, dragging, orbSize, handlers } = useDraggableAI(() => {
    if (open) {
      closeAssistant();
    } else {
      openAssistant();
    }
  });

  if (open) {
    return null;
  }

  return (
    <button
      type="button"
      aria-label="Open AI assistant"
      title="AI Assistant"
      className={`fixed z-[60] rounded-full ai-orb-glow animate-ai-orb-glow-pulse focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 transition-transform duration-200 ${
        dragging ? "cursor-grabbing scale-110" : "cursor-grab hover:scale-110"
      }`}
      style={{
        left: position.x,
        top: position.y,
        width: orbSize,
        height: orbSize,
        touchAction: "none",
      }}
      {...handlers}
    >
      <span className="sr-only">Open AI assistant</span>
      <span className="block h-full w-full animate-ai-orb-float">
        <Image
          src="/ai/assistant-orb.png"
          alt=""
          width={orbSize}
          height={orbSize}
          className="pointer-events-none select-none rounded-full"
          draggable={false}
          priority
        />
      </span>
    </button>
  );
}

"use client";

import Image from "next/image";
import { useAuth } from "@/hooks/useAuth";

function greetingForNow(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

const SUGGESTIONS = [
  "What position did Anny Stevia hold during her internship?",
  "Where is the Talent Performer office located?",
  "Summarize what you know from company documents.",
];

export function AIAssistantWelcome({
  onPickSuggestion,
}: {
  onPickSuggestion: (text: string) => void;
}) {
  const { user } = useAuth();
  const name = user?.first_name || user?.full_name?.split(" ")[0] || "there";

  return (
    <div className="h-full min-h-0 flex flex-col items-center justify-center text-center px-4 py-4 sm:py-6 overflow-hidden animate-dash-fade-up">
      <div className="relative mb-4 shrink-0">
        <div className="absolute inset-0 rounded-full bg-brand-500/15 blur-2xl scale-125" />
        <Image
          src="/ai/welcome-orb.png"
          alt=""
          width={112}
          height={112}
          className="relative ai-orb-float drop-shadow-lg mix-blend-screen"
          priority
        />
      </div>
      <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-brand-900 shrink-0">
        {greetingForNow()}, {name}
      </h1>
      <p className="mt-2 text-sm sm:text-base text-brand-300 max-w-md shrink-0">
        How can I help you with{" "}
        <span className="text-brand-600 font-medium">company knowledge</span> today?
      </p>

      <div className="mt-6 w-full max-w-2xl shrink-0">
        <p className="text-xs font-semibold uppercase tracking-wide text-brand-300 mb-2.5 text-left">
          Suggested questions
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
          {SUGGESTIONS.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => onPickSuggestion(item)}
              className="rounded-2xl border border-brand-200 bg-white/80 px-3.5 py-2.5 text-left text-sm text-brand-900 shadow-sm hover:border-brand-500/40 hover:shadow-md transition"
            >
              {item}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

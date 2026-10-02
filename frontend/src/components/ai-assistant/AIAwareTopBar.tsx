"use client";

import { Search } from "lucide-react";
import { NotificationBell } from "@/components/NotificationBell";
import { UserMenu } from "@/components/UserMenu";
import { useAIAssistant } from "@/hooks/useAIAssistant";

type AIAwareTopBarProps = {
  notificationVariant: "hr" | "employee";
  editProfileHref: string;
};

/** Shared portal top bar: shows Pulse + Close when the panel is open. */
export function AIAwareTopBar({
  notificationVariant,
  editProfileHref,
}: AIAwareTopBarProps) {
  const {
    open,
    closeAssistant,
    clearConversation,
    hasConversation,
    conversationId,
    loading,
  } = useAIAssistant();
  const canClear = hasConversation || conversationId != null;
  const showSearch = notificationVariant === "hr" && !open;

  return (
    <header className="shrink-0 border-b border-brand-200/80 bg-white">
      <div className="flex h-14 items-center justify-between gap-3 px-5 sm:px-6">
        <div className="min-w-0 flex-1">
          {open ? (
            <p className="truncate text-sm font-semibold text-brand-900">Pulse</p>
          ) : showSearch ? (
            <label className="relative block w-full max-w-xl">
              <span className="sr-only">Search</span>
              <Search
                className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-brand-300"
                aria-hidden
              />
              <input
                type="search"
                placeholder="Search employees, applications, documents..."
                className="h-9 w-full rounded-xl border border-transparent bg-[#f3f6f5] py-2 pl-9 pr-3 text-sm text-brand-900 outline-none transition placeholder:text-brand-300 focus:border-brand-200 focus:bg-white focus:ring-2 focus:ring-brand-500/15"
              />
            </label>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-2.5 sm:gap-3">
          {open ? (
            <>
              {canClear ? (
                <button
                  type="button"
                  disabled={loading}
                  title="Clear current conversation and start a new chat"
                  aria-label="Clear current conversation and start a new chat"
                  onClick={() => void clearConversation()}
                  className="rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-sm text-brand-900 transition hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  New chat
                </button>
              ) : null}
              <button
                type="button"
                onClick={closeAssistant}
                className="rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-sm text-brand-900 transition hover:bg-brand-50"
              >
                Close
              </button>
            </>
          ) : null}
          <NotificationBell variant={notificationVariant} />
          <UserMenu editProfileHref={editProfileHref} />
        </div>
      </div>
    </header>
  );
}

"use client";

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

  return (
    <header className="bg-white border-b border-brand-200 shrink-0">
      <div className="px-6 h-14 flex items-center justify-between gap-3">
        <div className="min-w-0">
          {open ? (
            <p className="text-sm font-semibold text-brand-900 truncate">Pulse</p>
          ) : null}
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {open ? (
            <>
              {canClear ? (
                <button
                  type="button"
                  disabled={loading}
                  title="Clear current conversation and start a new chat"
                  aria-label="Clear current conversation and start a new chat"
                  onClick={() => void clearConversation()}
                  className="rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-sm text-brand-900 hover:bg-brand-50 transition disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  New chat
                </button>
              ) : null}
              <button
                type="button"
                onClick={closeAssistant}
                className="rounded-lg border border-brand-200 bg-white px-3 py-1.5 text-sm text-brand-900 hover:bg-brand-50 transition"
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

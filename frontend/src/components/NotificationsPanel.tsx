"use client";

import Link from "next/link";
import { formatRelativeTime } from "@/lib/time";
import type { Notification } from "@/types/notifications";

interface NotificationsPanelProps {
  notifications: Notification[];
  loading: boolean;
  expandedId: number | null;
  navigating?: boolean;
  ctaLabel?: string;
  onNotificationClick: (notification: Notification) => void;
  onOpenRelated: (notification: Notification) => void;
  onClose: () => void;
  viewAllHref?: string;
}

export function NotificationsPanel({
  notifications,
  loading,
  expandedId,
  navigating = false,
  ctaLabel = "View details",
  onNotificationClick,
  onOpenRelated,
  onClose,
  viewAllHref = "/careers/notifications",
}: NotificationsPanelProps) {
  return (
    <div className="absolute right-0 mt-2 w-80 sm:w-96 overflow-hidden rounded-xl border border-[#0f224a]/20 bg-white z-50 shadow-[0_18px_40px_-18px_rgba(15,34,74,0.55),0_0_0_1px_rgba(15,34,74,0.06)]">
      <div className="flex items-center justify-between border-b border-[#0f224a]/10 bg-[#0f224a] px-4 py-3">
        <h2 className="text-sm font-semibold text-white">Notifications</h2>
        <Link
          href={viewAllHref}
          onClick={onClose}
          className="text-xs font-medium text-white/80 transition hover:text-white"
        >
          View all
        </Link>
      </div>

      {loading ? (
        <div className="py-10 flex justify-center">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[#0f224a]" />
        </div>
      ) : notifications.length === 0 ? (
        <p className="px-4 py-8 text-sm text-[#0f224a]/55 text-center">No notifications yet.</p>
      ) : (
        <ul className="max-h-96 overflow-y-auto divide-y divide-[#0f224a]/08">
          {notifications.slice(0, 8).map((notification) => {
            const expanded = expandedId === notification.id;
            return (
              <li key={notification.id}>
                <button
                  type="button"
                  onClick={() => onNotificationClick(notification)}
                  className={`w-full text-left px-4 py-3 transition hover:bg-[#0f224a]/06 ${
                    notification.is_read ? "bg-white" : "bg-[rgba(15,34,74,0.04)]"
                  }`}
                >
                  <p
                    className={`text-sm ${
                      notification.is_read
                        ? "font-medium text-[#0f224a]/80"
                        : "font-semibold text-[#0f224a]"
                    }`}
                  >
                    {notification.title}
                  </p>
                  <p className={`mt-1 text-xs text-[#0f224a]/60 ${expanded ? "" : "line-clamp-2"}`}>
                    {notification.message}
                  </p>
                  <p className="mt-1 text-xs text-[#0f224a]/40">{formatRelativeTime(notification.created_at)}</p>
                </button>
                {expanded && (
                  <div className="border-t border-[#0f224a]/10 bg-[rgba(15,34,74,0.03)] px-4 pb-3">
                    <p className="pt-3 text-sm text-[#0f224a]/85 whitespace-pre-wrap">{notification.message}</p>
                    {(notification.related_entity_type === "application" ||
                      notification.related_entity_type === "interview" ||
                      notification.related_entity_type === "onboarding") && (
                      <button
                        type="button"
                        disabled={navigating}
                        onClick={() => onOpenRelated(notification)}
                        className="mt-3 inline-flex rounded-lg bg-[#0f224a] px-3 py-1.5 text-xs font-medium text-white transition hover:bg-[#16305f] disabled:opacity-50"
                      >
                        {navigating ? "Opening..." : ctaLabel}
                      </button>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

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
    <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-white rounded-xl border shadow-lg z-50 overflow-hidden">
      <div className="px-4 py-3 border-b flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-900">Notifications</h2>
        <Link
          href={viewAllHref}
          onClick={onClose}
          className="text-xs text-red-600 hover:text-red-700"
        >
          View all
        </Link>
      </div>

      {loading ? (
        <div className="py-10 flex justify-center">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-brand-600" />
        </div>
      ) : notifications.length === 0 ? (
        <p className="px-4 py-8 text-sm text-gray-500 text-center">No notifications yet.</p>
      ) : (
        <ul className="max-h-96 overflow-y-auto divide-y divide-gray-100">
          {notifications.slice(0, 8).map((notification) => {
            const expanded = expandedId === notification.id;
            return (
              <li key={notification.id}>
                <button
                  type="button"
                  onClick={() => onNotificationClick(notification)}
                  className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition ${
                    notification.is_read ? "bg-white" : "bg-red-50"
                  }`}
                >
                  <p
                    className={`text-sm ${
                      notification.is_read ? "font-medium text-gray-800" : "font-semibold text-gray-900"
                    }`}
                  >
                    {notification.title}
                  </p>
                  <p className={`mt-1 text-xs text-gray-600 ${expanded ? "" : "line-clamp-2"}`}>
                    {notification.message}
                  </p>
                  <p className="mt-1 text-xs text-gray-400">{formatRelativeTime(notification.created_at)}</p>
                </button>
                {expanded && (
                  <div className="px-4 pb-3 bg-amber-50 border-t border-amber-100">
                    <p className="pt-3 text-sm text-amber-950 whitespace-pre-wrap">{notification.message}</p>
                    {(notification.related_entity_type === "application" ||
                      notification.related_entity_type === "interview") && (
                      <button
                        type="button"
                        disabled={navigating}
                        onClick={() => onOpenRelated(notification)}
                        className="mt-3 inline-flex bg-brand-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-brand-700 disabled:opacity-50"
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

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { formatRelativeTime } from "@/lib/time";
import { api } from "@/lib/api";
import type { Notification } from "@/types/notifications";

export default function NotificationsPage() {
  const router = useRouter();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [markingAll, setMarkingAll] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setNotifications(await api.listNotifications());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load notifications");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleMarkAllRead = async () => {
    setMarkingAll(true);
    try {
      await api.markAllNotificationsRead();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to mark notifications as read");
    } finally {
      setMarkingAll(false);
    }
  };

  const handleClick = async (notification: Notification) => {
    try {
      if (!notification.is_read) {
        await api.markNotificationRead(notification.id);
        setNotifications((items) =>
          items.map((item) =>
            item.id === notification.id ? { ...item, is_read: true, read_at: new Date().toISOString() } : item
          )
        );
      }

      if (notification.related_entity_type === "application" && notification.related_entity_id) {
        const application = await api.getMyApplication(notification.related_entity_id);
        router.push(`/careers/jobs/${application.job.id}`);
      } else if (notification.related_entity_type === "interview" && notification.related_entity_id) {
        router.push(`/careers/interviews/${notification.related_entity_id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open notification");
    }
  };

  const unreadCount = notifications.filter((item) => !item.is_read).length;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link href="/careers/jobs" className="text-sm text-gray-500 hover:text-gray-800">
            Careers
          </Link>
          <h1 className="mt-2 text-2xl font-bold text-gray-900">Notifications</h1>
          <p className="mt-1 text-sm text-gray-600">
            {unreadCount > 0 ? `${unreadCount} unread` : "You're all caught up"}
          </p>
        </div>
        {unreadCount > 0 && (
          <button
            type="button"
            onClick={handleMarkAllRead}
            disabled={markingAll}
            className="text-sm text-red-600 hover:text-red-700 disabled:opacity-50"
          >
            {markingAll ? "Marking..." : "Mark all as read"}
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{error}</div>
      )}

      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-16 flex justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
          </div>
        ) : notifications.length === 0 ? (
          <p className="py-16 text-center text-sm text-gray-500">No notifications yet.</p>
        ) : (
          <ul className="divide-y divide-gray-200">
            {notifications.map((notification) => (
              <li key={notification.id}>
                <button
                  type="button"
                  onClick={() => handleClick(notification)}
                  className={`w-full text-left px-5 py-4 hover:bg-gray-50 transition ${
                    notification.is_read ? "" : "bg-red-50"
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p
                        className={`text-sm ${
                          notification.is_read ? "font-medium text-gray-800" : "font-semibold text-gray-900"
                        }`}
                      >
                        {notification.title}
                      </p>
                      <p className="mt-1 text-sm text-gray-600">{notification.message}</p>
                    </div>
                    {!notification.is_read && (
                      <span className="inline-flex shrink-0 rounded-full h-2.5 w-2.5 bg-red-600 mt-1.5" />
                    )}
                  </div>
                  <p className="mt-2 text-xs text-gray-400">{formatRelativeTime(notification.created_at)}</p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

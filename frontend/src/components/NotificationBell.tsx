"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { NotificationsPanel } from "@/components/NotificationsPanel";
import { api } from "@/lib/api";
import type { Notification } from "@/types/notifications";

type NotificationBellProps = {
  variant?: "candidate" | "hr";
};

export function NotificationBell({ variant = "candidate" }: NotificationBellProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const refreshUnreadCount = useCallback(async () => {
    try {
      const data = await api.getUnreadNotificationCount();
      setUnreadCount(data.count);
    } catch {
      setUnreadCount(0);
    }
  }, []);

  const loadNotifications = useCallback(async () => {
    setLoading(true);
    try {
      setNotifications(await api.listNotifications());
    } catch {
      setNotifications([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUnreadCount();
  }, [refreshUnreadCount]);

  useEffect(() => {
    if (!open) return;
    loadNotifications();
  }, [open, loadNotifications]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const handleNotificationClick = async (notification: Notification) => {
    try {
      if (!notification.is_read) {
        await api.markNotificationRead(notification.id);
        setUnreadCount((count) => Math.max(0, count - 1));
        setNotifications((items) =>
          items.map((item) =>
            item.id === notification.id ? { ...item, is_read: true, read_at: new Date().toISOString() } : item
          )
        );
      }

      setOpen(false);

      if (variant === "candidate") {
        if (notification.related_entity_type === "application" && notification.related_entity_id) {
          const application = await api.getMyApplication(notification.related_entity_id);
          router.push(`/careers/jobs/${application.job.id}`);
        } else if (notification.related_entity_type === "interview" && notification.related_entity_id) {
          router.push(`/careers/interviews/${notification.related_entity_id}`);
        }
      } else if (notification.related_entity_type === "interview" && notification.related_entity_id) {
        const interview = await api.getInterview(notification.related_entity_id);
        router.push(`/hr/applications/${interview.application_id}`);
      }
    } catch {
      setOpen(false);
    }
  };

  const viewAllHref = variant === "hr" ? "/hr/notifications" : "/careers/notifications";

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="relative p-2 rounded-lg border border-gray-300 hover:bg-gray-50 transition text-gray-700"
        aria-label="Notifications"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-5 w-5">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.8}
            d="M15 17h5l-1.4-1.4A2 2 0 0 1 18 14.2V11a6 6 0 1 0-12 0v3.2c0 .5-.2 1-.6 1.4L4 17h5m6 0a3 3 0 0 1-6 0m6 0H9"
          />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 rounded-full text-[10px] font-semibold bg-red-600 text-white">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <NotificationsPanel
          notifications={notifications}
          loading={loading}
          onNotificationClick={handleNotificationClick}
          onClose={() => setOpen(false)}
          viewAllHref={viewAllHref}
        />
      )}
    </div>
  );
}

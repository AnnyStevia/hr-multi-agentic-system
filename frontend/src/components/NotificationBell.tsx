"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { NotificationsPanel } from "@/components/NotificationsPanel";
import { api } from "@/lib/api";
import type { Notification } from "@/types/notifications";

const POLL_INTERVAL_MS = 20_000;

type NotificationBellProps = {
  variant?: "candidate" | "hr" | "employee";
};

export function NotificationBell({ variant = "candidate" }: NotificationBellProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [navigating, setNavigating] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const openRef = useRef(open);
  openRef.current = open;

  const refreshUnreadCount = useCallback(async () => {
    try {
      const data = await api.getUnreadNotificationCount();
      setUnreadCount(data.count);
    } catch {
      setUnreadCount(0);
    }
  }, []);

  const loadNotifications = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      setNotifications(await api.listNotifications());
    } catch {
      setNotifications([]);
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUnreadCount();
    const interval = window.setInterval(() => {
      void refreshUnreadCount();
      if (openRef.current) {
        void loadNotifications(true);
      }
    }, POLL_INTERVAL_MS);

    const onVisible = () => {
      if (document.visibilityState === "visible") {
        void refreshUnreadCount();
        if (openRef.current) {
          void loadNotifications(true);
        }
      }
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refreshUnreadCount, loadNotifications]);

  useEffect(() => {
    if (!open) {
      setExpandedId(null);
      return;
    }
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

  const markReadLocally = async (notification: Notification) => {
    if (notification.is_read) return;
    await api.markNotificationRead(notification.id);
    setUnreadCount((count) => Math.max(0, count - 1));
    setNotifications((items) =>
      items.map((item) =>
        item.id === notification.id ? { ...item, is_read: true, read_at: new Date().toISOString() } : item
      )
    );
  };

  const handleNotificationClick = async (notification: Notification) => {
    if (notification.related_entity_type === "leave_request") {
      await navigateFromNotification(notification);
      return;
    }
    try {
      await markReadLocally(notification);
      setExpandedId((current) => (current === notification.id ? null : notification.id));
    } catch {
      // keep panel open
    }
  };

  const navigateFromNotification = async (notification: Notification) => {
    setNavigating(true);
    try {
      await markReadLocally(notification);
      setOpen(false);

      if (variant === "employee") {
        if (
          notification.related_entity_type === "onboarding" ||
          notification.related_entity_type === "onboarding_training"
        ) {
          router.push("/employee/onboarding");
        } else if (notification.related_entity_type === "leave_request") {
          router.push("/employee/leave");
        } else if (notification.related_entity_type === "interview" && notification.related_entity_id) {
          router.push(`/employee/interviews/${notification.related_entity_id}`);
        }
      } else if (variant === "candidate") {
        if (notification.related_entity_type === "application" && notification.related_entity_id) {
          const application = await api.getMyApplication(notification.related_entity_id);
          router.push(`/careers/jobs/${application.job.id}`);
        } else if (notification.related_entity_type === "interview" && notification.related_entity_id) {
          router.push(`/careers/interviews/${notification.related_entity_id}`);
        }
      } else if (notification.related_entity_type === "application" && notification.related_entity_id) {
        router.push(`/hr/applications/${notification.related_entity_id}`);
      } else if (notification.related_entity_type === "onboarding" && notification.related_entity_id) {
        router.push(`/hr/onboarding/${notification.related_entity_id}`);
      } else if (notification.related_entity_type === "leave_request") {
        router.push("/hr/leave");
      } else if (notification.related_entity_type === "interview" && notification.related_entity_id) {
        if (
          notification.type === "interview_assignment" ||
          notification.type === "interview_meeting_ready"
        ) {
          router.push(`/employee/interviews/${notification.related_entity_id}`);
        } else {
          const interview = await api.getInterview(notification.related_entity_id);
          router.push(`/hr/applications/${interview.application_id}`);
        }
      }
    } catch {
      setOpen(false);
    } finally {
      setNavigating(false);
    }
  };

  const viewAllHref =
    variant === "hr" ? "/hr/notifications" : variant === "employee" ? "/employee/leave" : "/careers/notifications";
  const expanded = expandedId ? notifications.find((n) => n.id === expandedId) : undefined;
  const ctaLabel =
    variant === "employee"
      ? expanded?.related_entity_type === "leave_request"
        ? "View leave"
        : expanded?.related_entity_type === "interview"
          ? "View interview"
          : "View onboarding"
      : variant === "hr"
        ? expanded?.related_entity_type === "onboarding"
          ? "View onboarding"
          : expanded?.related_entity_type === "leave_request"
            ? "View leave"
            : expanded?.type === "interview_assignment"
              ? "Propose slots"
              : expanded?.type === "interview_meeting_ready"
                ? "Join interview"
                : "View application"
        : expanded?.related_entity_type === "interview"
          ? "View interview"
          : "View application";

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
          expandedId={expandedId}
          navigating={navigating}
          ctaLabel={ctaLabel}
          onNotificationClick={handleNotificationClick}
          onOpenRelated={navigateFromNotification}
          onClose={() => setOpen(false)}
          viewAllHref={viewAllHref}
        />
      )}
    </div>
  );
}

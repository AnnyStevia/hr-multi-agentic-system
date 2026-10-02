"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Clock3,
  FileText,
  GraduationCap,
  Network,
  Palmtree,
  Plane,
  UserRound,
  Video,
} from "lucide-react";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { OnLeaveBanner } from "@/components/OnLeaveBanner";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import { formatSlotRange } from "@/lib/interviews";
import { cn } from "@/lib/utils";
import type { InterviewSummary } from "@/types/interviews";
import type { LeaveBalance, LeaveRequest } from "@/types/leave";
import type { Notification } from "@/types/notifications";
import type { OnboardingProgress, OnboardingTask } from "@/types/onboarding";
import type { EmployeeProfile } from "@/types/profile";
import type { MyTrainingResource } from "@/types/training";

const OFFICE_IMAGE =
  "/images/careers/" +
  encodeURIComponent(
    "Moderne kantoorinrichting met houten bureaus, planten en akoestisch plafond.jpg"
  );

const LEAVE_COLORS = {
  approved: "#029870",
  pending: "#f59e0b",
  rejected: "#e11d48",
  cancelled: "#64748b",
};

const TRAINING_COLORS = ["#029870", "#f59e0b", "#0f224a", "#64748b"];

const AVATAR_TONES = [
  "bg-brand-600",
  "bg-[#0f224a]",
  "bg-teal-600",
  "bg-sky-600",
  "bg-emerald-700",
];

const card =
  "rounded-2xl border border-brand-200/70 bg-white shadow-[0_8px_24px_-18px_rgba(15,34,74,0.35)]";

type AttentionItem = {
  key: string;
  title: string;
  meta: string;
  href: string;
  badge: string;
  tone: "warning" | "info" | "danger";
};

type ActivityItem = {
  key: string;
  title: string;
  meta: string;
  href?: string;
  when: string;
  kind: "interview" | "leave" | "deadline" | "training";
};

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function greetingForHour(hour: number): string {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function MiniSpark({
  points,
  stroke = "#029870",
}: {
  points: number[];
  stroke?: string;
}) {
  const max = Math.max(...points, 1);
  const min = Math.min(...points, 0);
  const range = Math.max(max - min, 1);
  const w = 48;
  const h = 18;
  const d = points
    .map((p, i) => {
      const x = (i / Math.max(points.length - 1, 1)) * w;
      const y = h - ((p - min) / range) * (h - 2) - 1;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden className="opacity-80">
      <path d={d} fill="none" stroke={stroke} strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function safeCall<T>(promise: Promise<T>, fallback: T): Promise<T> {
  return promise.catch(() => fallback);
}

export default function EmployeeDashboardPage() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<EmployeeProfile | null>(null);
  const [leaveRequests, setLeaveRequests] = useState<LeaveRequest[]>([]);
  const [leaveBalances, setLeaveBalances] = useState<LeaveBalance[]>([]);
  const [trainings, setTrainings] = useState<MyTrainingResource[]>([]);
  const [onboardingProgress, setOnboardingProgress] =
    useState<OnboardingProgress | null>(null);
  const [onboardingTasks, setOnboardingTasks] = useState<OnboardingTask[]>([]);
  const [interviews, setInterviews] = useState<InterviewSummary[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const [
          profileResult,
          leaveResult,
          balancesResult,
          trainingsResult,
          progressResult,
          tasksResult,
          interviewsResult,
          notificationsResult,
          unreadResult,
        ] = await Promise.all([
          safeCall(api.getMyProfile(), null),
          safeCall(api.listMyLeaveRequests(), [] as LeaveRequest[]),
          safeCall(api.listMyLeaveBalances(), [] as LeaveBalance[]),
          safeCall(api.listMyTrainings(), [] as MyTrainingResource[]),
          safeCall(api.getMyOnboardingProgress(), null),
          safeCall(api.listMyOnboardingTasks(), [] as OnboardingTask[]),
          safeCall(api.listMyInterviews(), [] as InterviewSummary[]),
          safeCall(api.listNotifications(), [] as Notification[]),
          safeCall(api.getUnreadNotificationCount(), { count: 0 }),
        ]);

        setProfile(profileResult);
        setLeaveRequests(leaveResult);
        setLeaveBalances(balancesResult);
        setTrainings(trainingsResult);
        setOnboardingProgress(progressResult);
        setOnboardingTasks(tasksResult);
        setInterviews(interviewsResult);
        setNotifications(notificationsResult);
        setUnreadCount(unreadResult.count);

        if (
          !profileResult &&
          leaveResult.length === 0 &&
          trainingsResult.length === 0
        ) {
          setError("Some dashboard data could not be loaded.");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load dashboard");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const todayLabel = useMemo(
    () =>
      new Date()
        .toLocaleDateString(undefined, {
          weekday: "short",
          day: "numeric",
          month: "short",
        })
        .toUpperCase(),
    []
  );

  const greeting = useMemo(() => greetingForHour(new Date().getHours()), []);

  const daysAvailable = useMemo(
    () =>
      leaveBalances.reduce((sum, balance) => sum + (balance.days_available ?? 0), 0),
    [leaveBalances]
  );

  const pendingLeave = useMemo(
    () => leaveRequests.filter((request) => request.status === "pending").length,
    [leaveRequests]
  );

  const pendingTrainings = useMemo(
    () => trainings.filter((item) => item.status === "pending").length,
    [trainings]
  );

  const onboardingPercent = onboardingProgress?.overall_percentage ?? 0;
  const hasActiveOnboarding =
    onboardingProgress != null &&
    onboardingProgress.status !== "completed" &&
    (onboardingProgress.tasks.total > 0 || onboardingPercent < 100);

  const leaveChart = useMemo(() => {
    const counts = {
      approved: 0,
      pending: 0,
      rejected: 0,
      cancelled: 0,
    };
    for (const request of leaveRequests) {
      if (request.status in counts) {
        counts[request.status as keyof typeof counts] += 1;
      }
    }
    return (
      [
        { name: "Approved", key: "approved" as const, value: counts.approved },
        { name: "Pending", key: "pending" as const, value: counts.pending },
        { name: "Rejected", key: "rejected" as const, value: counts.rejected },
        { name: "Cancelled", key: "cancelled" as const, value: counts.cancelled },
      ] as const
    ).filter((row) => row.value > 0);
  }, [leaveRequests]);

  const leaveTotal = useMemo(
    () => leaveChart.reduce((sum, row) => sum + row.value, 0),
    [leaveChart]
  );

  const trainingChart = useMemo(() => {
    const completed = trainings.filter((item) => item.status === "completed").length;
    const pending = trainings.filter((item) => item.status === "pending").length;
    return [
      { name: "Completed", value: completed },
      { name: "Pending", value: pending },
    ].filter((row) => row.value > 0);
  }, [trainings]);

  const attentionItems = useMemo((): AttentionItem[] => {
    const items: AttentionItem[] = [];

    if (unreadCount > 0) {
      items.push({
        key: "unread",
        title: `${unreadCount} unread notification${unreadCount === 1 ? "" : "s"}`,
        meta: "Check the bell in the top bar",
        href: "/employee/dashboard",
        badge: "Alerts",
        tone: "danger",
      });
    }

    for (const request of leaveRequests.filter((item) => item.status === "pending").slice(0, 2)) {
      items.push({
        key: `leave-${request.id}`,
        title: request.leave_type_name,
        meta: `${formatDate(request.start_date)} → ${formatDate(request.end_date)}`,
        href: "/employee/leave",
        badge: "Leave",
        tone: "warning",
      });
    }

    for (const task of onboardingTasks
      .filter((item) => item.status === "pending")
      .slice(0, 2)) {
      items.push({
        key: `task-${task.id}`,
        title: task.title,
        meta: task.due_date
          ? `Due ${formatDate(task.due_date)}`
          : "Onboarding task pending",
        href: "/employee/onboarding",
        badge: "Onboarding",
        tone: "info",
      });
    }

    for (const interview of interviews
      .filter(
        (item) =>
          item.can_propose_slots ||
          item.status === "proposed" ||
          (item.status === "scheduled" && !item.meeting_url)
      )
      .slice(0, 2)) {
      items.push({
        key: `int-${interview.id}`,
        title: interview.candidate_name,
        meta: interview.can_propose_slots
          ? "Propose interview slots"
          : interview.status_label,
        href: `/employee/interviews/${interview.id}`,
        badge: "Interview",
        tone: "warning",
      });
    }

    for (const training of trainings
      .filter((item) => item.status === "pending")
      .slice(0, 2)) {
      items.push({
        key: `tr-${training.training_id}`,
        title: training.title,
        meta: "Training assigned",
        href: "/employee/training",
        badge: "Training",
        tone: "info",
      });
    }

    return items.slice(0, 5);
  }, [unreadCount, leaveRequests, onboardingTasks, interviews, trainings]);

  const upcomingActivity = useMemo((): ActivityItem[] => {
    const items: ActivityItem[] = [];

    for (const interview of interviews) {
      if (interview.selected_slot) {
        items.push({
          key: `int-${interview.id}`,
          title: interview.candidate_name,
          meta: `Interview · ${interview.job_title}`,
          href: `/employee/interviews/${interview.id}`,
          when: formatSlotRange(
            interview.selected_slot.starts_at,
            interview.selected_slot.ends_at
          ),
          kind: "interview",
        });
      }
    }

    for (const task of onboardingTasks.filter(
      (item) => item.status === "pending" && item.due_date
    )) {
      items.push({
        key: `due-${task.id}`,
        title: task.title,
        meta: "Onboarding deadline",
        href: "/employee/onboarding",
        when: formatDate(task.due_date!),
        kind: "deadline",
      });
    }

    for (const request of leaveRequests.filter(
      (item) => item.status === "approved"
    )) {
      const end = new Date(`${request.end_date}T00:00:00`);
      const now = new Date();
      if (end >= now) {
        items.push({
          key: `leave-${request.id}`,
          title: request.leave_type_name,
          meta: `Leave · ${formatDate(request.start_date)} → ${formatDate(request.end_date)}`,
          href: "/employee/leave",
          when: formatDate(request.start_date),
          kind: "leave",
        });
      }
    }

    for (const training of trainings
      .filter((item) => item.status === "pending")
      .slice(0, 3)) {
      items.push({
        key: `tr-${training.training_id}`,
        title: training.title,
        meta: "Training",
        href: "/employee/training",
        when: "Assigned",
        kind: "training",
      });
    }

    return items.slice(0, 5);
  }, [interviews, onboardingTasks, leaveRequests, trainings]);

  const recentNotifications = useMemo(
    () => notifications.slice(0, 5),
    [notifications]
  );

  if (!user) return null;

  if (loading) {
    return (
      <div className="-m-6 flex min-h-[50vh] items-center justify-center bg-[#f3f6f5] p-6">
        <div className="flex items-center gap-2.5">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
          <p className="text-sm text-brand-300">Loading dashboard…</p>
        </div>
      </div>
    );
  }

  const roleLine = [profile?.position, profile?.department]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 pb-8 sm:p-6">
      <div className="mx-auto max-w-[1200px] space-y-5">
        <section className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-[#0b2a3a] via-[#0f3d48] to-[#117a5f]">
          <Image
            src={OFFICE_IMAGE}
            alt=""
            fill
            className="object-cover object-[center_35%] opacity-35"
            sizes="1200px"
            priority
          />
          <div className="absolute inset-0 bg-gradient-to-r from-[#0b2a3a]/95 via-[#0f3d48]/82 to-[#117a5f]/55" />
          <div className="relative flex flex-col gap-4 px-6 py-6 sm:flex-row sm:items-end sm:justify-between sm:px-7 sm:py-7">
            <div className="max-w-xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-white/60">
                {todayLabel}
              </p>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white sm:text-[1.85rem]">
                {greeting}, {user.first_name}
              </h1>
              <p className="mt-1.5 text-sm text-white/70">
                {roleLine
                  ? `${roleLine}. Here's your workspace overview.`
                  : "Here's what's next for you today."}
              </p>
            </div>
            <Button
              asChild
              className="h-10 w-fit gap-1.5 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white shadow-lg shadow-black/20 hover:bg-brand-700"
            >
              <Link href="/employee/leave">
                <Palmtree className="size-4" />
                Request leave
              </Link>
            </Button>
          </div>
        </section>

        {profile?.current_work_status === "ON_LEAVE" && profile.current_leave ? (
          <OnLeaveBanner currentLeave={profile.current_leave} />
        ) : null}

        {error ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {error}
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
          <KpiCard
            label="Leave days available"
            value={Math.round(daysAvailable)}
            icon={<Palmtree className="size-4" />}
            iconClass="bg-emerald-50 text-emerald-700"
            spark={[4, 5, 4, 6, 5, 7, 6]}
            sparkColor="#029870"
          />
          <KpiCard
            label="Pending leave requests"
            value={pendingLeave}
            icon={<Clock3 className="size-4" />}
            iconClass="bg-amber-50 text-amber-700"
            spark={[2, 1, 2, 3, 2, 1, 2]}
            sparkColor="#f59e0b"
          />
          <KpiCard
            label="Pending trainings"
            value={pendingTrainings}
            icon={<BookOpen className="size-4" />}
            iconClass="bg-teal-50 text-teal-700"
            spark={[1, 2, 1, 2, 3, 2, 2]}
            sparkColor="#0d9488"
          />
          <KpiCard
            label={hasActiveOnboarding ? "Onboarding progress" : "Unread alerts"}
            value={hasActiveOnboarding ? onboardingPercent : unreadCount}
            suffix={hasActiveOnboarding ? "%" : undefined}
            icon={
              hasActiveOnboarding ? (
                <GraduationCap className="size-4" />
              ) : (
                <ClipboardList className="size-4" />
              )
            }
            iconClass="bg-sky-50 text-sky-700"
            spark={[3, 4, 5, 6, 7, 8, 9]}
            sparkColor="#0ea5e9"
          />
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <section className={card}>
            <div className="flex items-center justify-between gap-2 px-4 pb-2 pt-4">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-brand-900">Needs attention</h2>
                <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-rose-500 px-1.5 text-[11px] font-semibold text-white">
                  {attentionItems.length}
                </span>
              </div>
              <Link
                href="/employee/onboarding"
                className="text-xs font-medium text-brand-600 hover:text-brand-700"
              >
                View tasks
              </Link>
            </div>
            <div className="px-2 pb-3">
              {attentionItems.length === 0 ? (
                <EmptyState message="You're all caught up." />
              ) : (
                <ul className="space-y-0.5">
                  {attentionItems.map((item, index) => (
                    <li key={item.key}>
                      <Link
                        href={item.href}
                        className="flex items-center gap-2.5 rounded-xl px-2 py-2 transition hover:bg-[#f6f9f8]"
                      >
                        <Avatar className="h-8 w-8">
                          <AvatarFallback
                            className={cn(
                              "text-[10px] text-white",
                              AVATAR_TONES[index % AVATAR_TONES.length]
                            )}
                          >
                            {initials(item.title)}
                          </AvatarFallback>
                        </Avatar>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[13px] font-semibold text-brand-900">
                            {item.title}
                          </p>
                          <p className="truncate text-[11px] text-brand-300">
                            {item.meta}
                          </p>
                        </div>
                        <Badge
                          variant={
                            item.tone === "warning"
                              ? "warning"
                              : item.tone === "info"
                                ? "info"
                                : "danger"
                          }
                          className="shrink-0 rounded-full px-2 text-[10px]"
                        >
                          {item.badge}
                        </Badge>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <DonutCard
            title="My leave by status"
            centerLabel={`${leaveTotal}`}
            centerHint="requests"
            empty={leaveChart.length === 0}
            data={[...leaveChart]}
            colors={leaveChart.map((row) => LEAVE_COLORS[row.key])}
            legend={(
              [
                ["Approved", leaveRequests.filter((r) => r.status === "approved").length, "approved"],
                ["Pending", leaveRequests.filter((r) => r.status === "pending").length, "pending"],
                ["Rejected", leaveRequests.filter((r) => r.status === "rejected").length, "rejected"],
              ] as const
            ).map(([name, value, key]) => ({
              name,
              value: `${value}`,
              color: LEAVE_COLORS[key],
            }))}
          />

          <DonutCard
            title="Training progress"
            centerLabel={`${trainings.length}`}
            centerHint="courses"
            empty={trainingChart.length === 0}
            data={trainingChart}
            colors={TRAINING_COLORS}
            legend={trainingChart.map((row, index) => ({
              name: row.name,
              value: `${row.value}`,
              color: TRAINING_COLORS[index % TRAINING_COLORS.length],
            }))}
          />
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <section className={card}>
            <div className="flex items-start justify-between gap-2 px-4 pb-1 pt-4">
              <div>
                <h2 className="text-sm font-semibold text-brand-900">Recent updates</h2>
                <p className="text-[11px] text-brand-300">Latest notifications</p>
              </div>
            </div>
            <div className="px-2 pb-3">
              {recentNotifications.length === 0 ? (
                <EmptyState message="No recent updates." />
              ) : (
                <ul className="space-y-0.5">
                  {recentNotifications.map((item, index) => (
                    <li key={item.id}>
                      <div className="flex items-center gap-2.5 rounded-xl px-2 py-2">
                        <Avatar className="h-8 w-8">
                          <AvatarFallback
                            className={cn(
                              "text-[10px] text-white",
                              AVATAR_TONES[index % AVATAR_TONES.length]
                            )}
                          >
                            {item.is_read ? "✓" : "!"}
                          </AvatarFallback>
                        </Avatar>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[13px] font-semibold text-brand-900">
                            {item.title}
                          </p>
                          <p className="truncate text-[11px] text-brand-300">
                            {item.message}
                          </p>
                        </div>
                        <span className="shrink-0 text-[11px] text-brand-300">
                          {formatDateTime(item.created_at)}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <section className={card}>
            <div className="flex items-start justify-between gap-2 px-4 pb-1 pt-4">
              <div>
                <h2 className="text-sm font-semibold text-brand-900">Upcoming</h2>
                <p className="text-[11px] text-brand-300">
                  Interviews, leave, deadlines
                </p>
              </div>
              <Link
                href="/employee/interviews"
                className="text-xs font-medium text-brand-600 hover:text-brand-700"
              >
                View all
              </Link>
            </div>
            <div className="px-2 pb-3">
              {upcomingActivity.length === 0 ? (
                <EmptyState message="Nothing scheduled soon." />
              ) : (
                <ul className="space-y-0.5">
                  {upcomingActivity.map((item) => (
                    <li key={item.key}>
                      <ActivityRow item={item} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <section className={card}>
            <div className="px-4 pb-1 pt-4">
              <h2 className="text-sm font-semibold text-brand-900">Quick actions</h2>
              <p className="text-[11px] text-brand-300">Common employee tasks</p>
            </div>
            <div className="space-y-0.5 px-2 pb-3">
              <ActionRow
                href="/employee/leave"
                icon={<Palmtree className="size-3.5" />}
                label="Request leave"
                tone="bg-emerald-50 text-emerald-700"
              />
              <ActionRow
                href="/employee/profile"
                icon={<UserRound className="size-3.5" />}
                label="Update my profile"
                tone="bg-slate-100 text-brand-800"
              />
              <ActionRow
                href="/employee/documents"
                icon={<FileText className="size-3.5" />}
                label="My documents"
                tone="bg-sky-50 text-sky-700"
              />
              <ActionRow
                href="/employee/training"
                icon={<GraduationCap className="size-3.5" />}
                label="Browse training"
                tone="bg-teal-50 text-teal-700"
              />
              <ActionRow
                href="/employee/organization"
                icon={<Network className="size-3.5" />}
                label="View organization"
                tone="bg-amber-50 text-amber-700"
              />
              <ActionRow
                href="/employee/interviews"
                icon={<Video className="size-3.5" />}
                label="My interviews"
                tone="bg-rose-50 text-rose-700"
              />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function KpiCard({
  label,
  value,
  suffix,
  icon,
  iconClass,
  spark,
  sparkColor,
}: {
  label: string;
  value: number;
  suffix?: string;
  icon: ReactNode;
  iconClass: string;
  spark: number[];
  sparkColor: string;
}) {
  return (
    <div className={cn(card, "px-4 py-3.5")}>
      <div className="flex items-start justify-between gap-3">
        <div
          className={cn(
            "flex h-9 w-9 items-center justify-center rounded-xl",
            iconClass
          )}
        >
          {icon}
        </div>
        <MiniSpark points={spark} stroke={sparkColor} />
      </div>
      <p className="mt-3 text-2xl font-semibold tabular-nums tracking-tight text-brand-900">
        {value}
        {suffix ? <span className="text-base font-semibold">{suffix}</span> : null}
      </p>
      <p className="mt-0.5 text-[12px] text-brand-300">{label}</p>
    </div>
  );
}

function DonutCard({
  title,
  centerLabel,
  centerHint,
  empty,
  data,
  colors,
  legend,
}: {
  title: string;
  centerLabel: string;
  centerHint: string;
  empty: boolean;
  data: Array<{ name: string; value: number }>;
  colors: string[];
  legend: Array<{ name: string; value: string; meta?: string; color: string }>;
}) {
  return (
    <section className={card}>
      <div className="px-4 pb-1 pt-4">
        <h2 className="text-sm font-semibold text-brand-900">{title}</h2>
      </div>
      <div className="px-4 pb-4 pt-2">
        {empty ? (
          <EmptyState message="No data yet." />
        ) : (
          <div className="grid grid-cols-[120px_1fr] items-center gap-3">
            <div className="relative mx-auto h-[120px] w-[120px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={data}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={38}
                    outerRadius={54}
                    paddingAngle={2}
                    strokeWidth={0}
                    animationDuration={500}
                  >
                    {data.map((entry, index) => (
                      <Cell
                        key={entry.name}
                        fill={colors[index % colors.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: number, name: string) => [`${value}`, name]}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
                <p className="text-base font-semibold tabular-nums text-brand-900">
                  {centerLabel}
                </p>
                <p className="text-[10px] text-brand-300">{centerHint}</p>
              </div>
            </div>
            <ul className="space-y-2">
              {legend.map((row) => (
                <li
                  key={row.name}
                  className="flex items-center justify-between gap-2 text-[12px]"
                >
                  <div className="flex min-w-0 items-center gap-1.5">
                    <span
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{ backgroundColor: row.color }}
                    />
                    <span className="truncate text-brand-900">{row.name}</span>
                  </div>
                  <span className="shrink-0 tabular-nums text-brand-700">
                    {row.value}
                    {row.meta ? (
                      <span className="text-brand-300"> · {row.meta}</span>
                    ) : null}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-8">
      <CheckCircle2 className="size-4 text-brand-500" />
      <p className="text-[13px] text-brand-300">{message}</p>
    </div>
  );
}

function ActivityRow({ item }: { item: ActivityItem }) {
  const icon =
    item.kind === "interview" ? (
      <CalendarDays className="size-3.5" />
    ) : item.kind === "leave" ? (
      <Plane className="size-3.5" />
    ) : item.kind === "training" ? (
      <GraduationCap className="size-3.5" />
    ) : (
      <ClipboardList className="size-3.5" />
    );

  const tone =
    item.kind === "interview"
      ? "bg-sky-50 text-sky-700"
      : item.kind === "leave"
        ? "bg-emerald-50 text-emerald-700"
        : item.kind === "training"
          ? "bg-teal-50 text-teal-700"
          : "bg-amber-50 text-amber-700";

  const content = (
    <div className="flex items-center gap-2.5 rounded-xl px-2 py-2 transition hover:bg-[#f6f9f8]">
      <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-xl", tone)}>
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-semibold text-brand-900">{item.title}</p>
        <p className="truncate text-[11px] text-brand-300">{item.meta}</p>
      </div>
      <span className="shrink-0 text-[11px] text-brand-300">{item.when}</span>
    </div>
  );

  if (item.href) return <Link href={item.href}>{content}</Link>;
  return content;
}

function ActionRow({
  href,
  icon,
  label,
  tone,
}: {
  href: string;
  icon: ReactNode;
  label: string;
  tone: string;
}) {
  return (
    <Link
      href={href}
      className="group flex items-center gap-2.5 rounded-xl px-2 py-2.5 transition hover:bg-[#f6f9f8]"
    >
      <span
        className={cn(
          "flex h-8 w-8 items-center justify-center rounded-xl",
          tone
        )}
      >
        {icon}
      </span>
      <span className="min-w-0 flex-1 text-[13px] font-medium text-brand-900">
        {label}
      </span>
      <ChevronRight className="size-4 text-brand-300 transition group-hover:text-brand-600" />
    </Link>
  );
}

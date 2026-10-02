"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Briefcase,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Clock3,
  FileText,
  GraduationCap,
  Plane,
  Plus,
  UserPlus,
  Users,
} from "lucide-react";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import type { HrDashboard } from "@/types/dashboard";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

const OFFICE_IMAGE =
  "/images/careers/" +
  encodeURIComponent(
    "Moderne kantoorinrichting met houten bureaus, planten en akoestisch plafond.jpg"
  );

const WORKFORCE_COLORS = ["#029870", "#0d9488", "#0f224a", "#38bdf8", "#f59e0b", "#64748b"];
const LEAVE_COLORS = {
  approved: "#029870",
  pending: "#f59e0b",
  rejected: "#e11d48",
};

const AVATAR_TONES = [
  "bg-brand-600",
  "bg-[#0f224a]",
  "bg-teal-600",
  "bg-sky-600",
  "bg-emerald-700",
];

const card =
  "rounded-2xl border border-brand-200/70 bg-white shadow-[0_8px_24px_-18px_rgba(15,34,74,0.35)]";

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

export default function HrDashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState<HrDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        setData(await api.getHrDashboard());
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

  const attentionItems = useMemo((): AttentionItem[] => {
    if (!data) return [];
    const items: AttentionItem[] = [];
    for (const item of data.attention.pending_leave) {
      items.push({
        key: `leave-${item.request_id}`,
        title: item.employee_name,
        meta: `${item.leave_type} · ${formatDate(item.start_date)}`,
        href: "/hr/leave",
        badge: "Leave",
        tone: "warning",
      });
    }
    for (const item of data.attention.incomplete_onboarding) {
      items.push({
        key: `onb-${item.onboarding_id}`,
        title: item.employee_name,
        meta: `${item.progress_percent}% · ${item.completed_tasks}/${item.total_tasks} tasks`,
        href: `/hr/onboarding/${item.onboarding_id}`,
        badge: "Onboarding",
        tone: "info",
      });
    }
    for (const item of data.attention.pending_applications) {
      items.push({
        key: `app-${item.application_id}`,
        title: item.candidate_name,
        meta: item.job_title,
        href: `/hr/applications/${item.application_id}`,
        badge: "Application",
        tone: "danger",
      });
    }
    return items.slice(0, 5);
  }, [data]);

  const workforceChart = useMemo(() => {
    const rows = data?.workforce.by_department ?? [];
    const total = rows.reduce((sum, row) => sum + row.count, 0) || 1;
    return rows.slice(0, 6).map((row) => ({
      name: row.label,
      value: row.count,
      percent: Math.round((row.count / total) * 100),
    }));
  }, [data]);

  const workforceTotal = useMemo(
    () => workforceChart.reduce((sum, row) => sum + row.value, 0),
    [workforceChart]
  );

  const leaveChart = useMemo(() => {
    const overview = data?.leave_overview;
    if (!overview) return [];
    return [
      { name: "Approved", key: "approved", value: overview.approved },
      { name: "Pending", key: "pending", value: overview.pending },
      { name: "Rejected", key: "rejected", value: overview.rejected },
    ].filter((row) => row.value > 0);
  }, [data]);

  const leaveTotal = useMemo(
    () =>
      (data?.leave_overview.approved ?? 0) +
      (data?.leave_overview.pending ?? 0) +
      (data?.leave_overview.rejected ?? 0),
    [data]
  );

  const upcomingActivity = useMemo((): ActivityItem[] => {
    if (!data) return [];
    const items: ActivityItem[] = [];
    for (const item of data.activity.upcoming_interviews) {
      items.push({
        key: `int-${item.interview_id}`,
        title: item.candidate_name,
        meta: `Interview · ${item.job_title}`,
        href: `/hr/applications/${item.application_id}`,
        when: formatDateTime(item.starts_at),
        kind: "interview",
      });
    }
    for (const item of data.activity.returning_soon) {
      items.push({
        key: `ret-${item.request_id}`,
        title: item.employee_name,
        meta: `Returning from ${item.leave_type}`,
        when: formatDate(item.end_date),
        kind: "leave",
      });
    }
    for (const item of data.activity.upcoming_deadlines ?? []) {
      items.push({
        key: `dl-${item.onboarding_id}-${item.task_title}-${item.due_date}`,
        title: item.employee_name,
        meta: `Deadline · ${item.task_title}`,
        href: `/hr/onboarding/${item.onboarding_id}`,
        when: formatDate(item.due_date),
        kind: "deadline",
      });
    }
    return items.slice(0, 5);
  }, [data]);

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

  const kpis = data?.kpis;

  return (
    <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 pb-8 sm:p-6">
      <div className="mx-auto max-w-[1200px] space-y-5">
        {/* Welcome banner */}
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
                Here&apos;s what&apos;s happening across your organization today.
              </p>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button className="h-10 w-fit gap-1.5 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white shadow-lg shadow-black/20 hover:bg-brand-700">
                  <Plus className="size-4" />
                  Create
                  <ChevronDown className="size-3.5 opacity-80" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Quick create</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link href="/hr/employees/create">
                    <UserPlus className="size-4" />
                    Add Employee
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link href="/hr/jobs/create">
                    <Briefcase className="size-4" />
                    Create Job
                  </Link>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </section>

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {/* KPI row */}
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
          <KpiCard
            label="Total employees"
            value={kpis?.total_employees ?? 0}
            icon={<Users className="size-4" />}
            iconClass="bg-emerald-50 text-emerald-700"
            spark={[3, 4, 3, 5, 6, 5, 7]}
            sparkColor="#029870"
          />
          <KpiCard
            label="On leave today"
            value={kpis?.on_leave ?? 0}
            icon={<CalendarDays className="size-4" />}
            iconClass="bg-sky-50 text-sky-700"
            spark={[2, 1, 2, 3, 2, 1, 1]}
            sparkColor="#0ea5e9"
          />
          <KpiCard
            label="Onboarding"
            value={kpis?.onboarding ?? 0}
            icon={<GraduationCap className="size-4" />}
            iconClass="bg-teal-50 text-teal-700"
            spark={[1, 1, 2, 2, 1, 1, 1]}
            sparkColor="#0d9488"
          />
          <KpiCard
            label="Pending leave approval"
            value={kpis?.pending_leave ?? 0}
            icon={<Clock3 className="size-4" />}
            iconClass="bg-amber-50 text-amber-700"
            spark={[4, 3, 4, 2, 3, 2, 2]}
            sparkColor="#f59e0b"
          />
        </div>

        {/* Middle row */}
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
                href="/hr/leave"
                className="text-xs font-medium text-brand-600 hover:text-brand-700"
              >
                View all
              </Link>
            </div>
            <div className="px-2 pb-3">
              {attentionItems.length === 0 ? (
                <EmptyState message="Nothing urgent right now." />
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
                          <p className="truncate text-[11px] text-brand-300">{item.meta}</p>
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
            title="Workforce by department"
            centerLabel={`${workforceTotal}`}
            centerHint="employees"
            empty={workforceChart.length === 0}
            data={workforceChart}
            colors={WORKFORCE_COLORS}
            legend={workforceChart.map((row, index) => ({
              name: row.name,
              value: `${row.value}`,
              meta: `${row.percent}%`,
              color: WORKFORCE_COLORS[index % WORKFORCE_COLORS.length],
            }))}
          />

          <DonutCard
            title="Leave by status"
            centerLabel={`${leaveTotal}`}
            centerHint="requests"
            empty={leaveChart.length === 0}
            data={leaveChart}
            colors={leaveChart.map(
              (row) => LEAVE_COLORS[row.key as keyof typeof LEAVE_COLORS]
            )}
            legend={(
              [
                ["Approved", data?.leave_overview.approved ?? 0, "approved"],
                ["Pending", data?.leave_overview.pending ?? 0, "pending"],
                ["Rejected", data?.leave_overview.rejected ?? 0, "rejected"],
              ] as const
            ).map(([name, value, key]) => ({
              name,
              value: `${value}`,
              color: LEAVE_COLORS[key],
            }))}
          />
        </div>

        {/* Bottom row */}
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <section className={card}>
            <div className="flex items-start justify-between gap-2 px-4 pb-1 pt-4">
              <div>
                <h2 className="text-sm font-semibold text-brand-900">Recent hires</h2>
                <p className="text-[11px] text-brand-300">Last 14 days</p>
              </div>
              <Link
                href="/hr/employees"
                className="text-xs font-medium text-brand-600 hover:text-brand-700"
              >
                View all
              </Link>
            </div>
            <div className="px-2 pb-3">
              {(data?.activity.recent_hires.length ?? 0) === 0 ? (
                <EmptyState message="No recent hires." />
              ) : (
                <ul className="space-y-0.5">
                  {data!.activity.recent_hires.slice(0, 5).map((hire, index) => (
                    <li key={hire.employee_id}>
                      <Link
                        href={`/hr/employees/${hire.employee_id}`}
                        className="flex items-center gap-2.5 rounded-xl px-2 py-2 transition hover:bg-[#f6f9f8]"
                      >
                        <Avatar className="h-8 w-8">
                          <AvatarFallback
                            className={cn(
                              "text-[10px] text-white",
                              AVATAR_TONES[index % AVATAR_TONES.length]
                            )}
                          >
                            {initials(hire.employee_name)}
                          </AvatarFallback>
                        </Avatar>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-[13px] font-semibold text-brand-900">
                            {hire.employee_name}
                          </p>
                          <p className="truncate text-[11px] text-brand-300">
                            {[hire.position, hire.department]
                              .filter(Boolean)
                              .join(" · ") || "—"}
                          </p>
                        </div>
                        <span className="shrink-0 text-[11px] text-brand-300">
                          {formatDate(hire.hire_date)}
                        </span>
                      </Link>
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
                  Interviews, returns, deadlines
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
              <p className="text-[11px] text-brand-300">Common HR tasks</p>
            </div>
            <div className="space-y-0.5 px-2 pb-3">
              <ActionRow
                href="/hr/employees/create"
                icon={<UserPlus className="size-3.5" />}
                label="Add employee"
                tone="bg-emerald-50 text-emerald-700"
              />
              <ActionRow
                href="/hr/jobs/create"
                icon={<Briefcase className="size-3.5" />}
                label="Create job opening"
                tone="bg-slate-100 text-brand-800"
              />
              <ActionRow
                href="/hr/leave"
                icon={<CalendarDays className="size-3.5" />}
                label="Review leave requests"
                tone="bg-amber-50 text-amber-700"
              />
              <ActionRow
                href="/hr/onboarding"
                icon={<GraduationCap className="size-3.5" />}
                label="Manage onboarding"
                tone="bg-teal-50 text-teal-700"
              />
              <ActionRow
                href="/hr/documents"
                icon={<FileText className="size-3.5" />}
                label="Browse documents"
                tone="bg-sky-50 text-sky-700"
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
  icon,
  iconClass,
  spark,
  sparkColor,
}: {
  label: string;
  value: number;
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

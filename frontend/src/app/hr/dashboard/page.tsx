"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Briefcase,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Plus,
  UserPlus,
  Users,
  Plane,
  GraduationCap,
  AlertCircle,
  Clock3,
  Sparkles,
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
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

const WORKFORCE_COLORS = [
  "#01785a",
  "#029870",
  "#0f224a",
  "#38bdf8",
  "#f59e0b",
  "#0d9488",
  "#64748b",
];

const LEAVE_COLORS = {
  approved: "#01785a",
  pending: "#f59e0b",
  rejected: "#e11d48",
};

const AVATAR_TONES = [
  "from-emerald-500 to-brand-700",
  "from-sky-500 to-brand-800",
  "from-amber-400 to-orange-600",
  "from-teal-500 to-cyan-700",
  "from-brand-600 to-brand-900",
];

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
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

function useCountUp(target: number, durationMs = 900): number {
  const [value, setValue] = useState(0);

  useEffect(() => {
    let frame = 0;
    const start = performance.now();
    const from = 0;
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(from + (target - from) * eased));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, durationMs]);

  return value;
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
  kind: "interview" | "leave" | "deadline";
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
      new Date().toLocaleDateString(undefined, {
        weekday: "long",
        month: "long",
        day: "numeric",
      }),
    []
  );

  const greeting = useMemo(
    () => greetingForHour(new Date().getHours()),
    []
  );

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
        meta: `${item.progress_percent}% complete · ${item.completed_tasks}/${item.total_tasks} tasks`,
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
    return items.slice(0, 8);
  }, [data]);

  const workforceChart = useMemo(() => {
    const rows = data?.workforce.by_department ?? [];
    const total = rows.reduce((sum, row) => sum + row.count, 0) || 1;
    return rows.slice(0, 7).map((row) => ({
      name: row.label,
      value: row.count,
      percent: Math.round((row.count / total) * 100),
    }));
  }, [data]);

  const leaveChart = useMemo(() => {
    const overview = data?.leave_overview;
    if (!overview) return [];
    return [
      { name: "Approved", key: "approved", value: overview.approved },
      { name: "Pending", key: "pending", value: overview.pending },
      { name: "Rejected", key: "rejected", value: overview.rejected },
    ].filter((row) => row.value > 0);
  }, [data]);

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
    return items.slice(0, 8);
  }, [data]);

  if (!user) return null;

  if (loading) {
    return (
      <div className="dash-mesh -m-6 flex min-h-[60vh] items-center justify-center p-6">
        <div className="flex flex-col items-center gap-3 animate-dash-fade-in">
          <div className="relative h-12 w-12">
            <div className="absolute inset-0 rounded-full border-2 border-brand-200" />
            <div className="absolute inset-0 animate-spin rounded-full border-2 border-transparent border-t-brand-600 border-r-sky-400" />
          </div>
          <p className="text-sm font-medium text-brand-800">Loading your workspace…</p>
        </div>
      </div>
    );
  }

  const kpis = data?.kpis;

  return (
    <div className="dash-mesh relative -m-6 min-h-full overflow-hidden p-6 pb-10">
      <div
        aria-hidden
        className="pointer-events-none absolute -right-16 top-8 h-56 w-56 rounded-full bg-gradient-to-br from-brand-500/20 to-sky-400/10 blur-3xl animate-dash-float"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -left-10 bottom-24 h-48 w-48 rounded-full bg-gradient-to-tr from-amber-300/20 to-brand-600/10 blur-3xl animate-dash-float [animation-delay:1.2s]"
      />

      <div className="relative mx-auto max-w-[1240px] space-y-6">
        <div
          className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between animate-dash-fade-up"
          style={{ animationDelay: "0ms" }}
        >
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-brand-200/80 bg-white/70 px-3 py-1 text-xs font-medium text-brand-700 shadow-sm backdrop-blur">
              <Sparkles className="size-3.5 text-amber-500 animate-dash-pulse-soft" />
              {todayLabel}
            </div>
            <h1 className="mt-3 bg-gradient-to-r from-brand-900 via-brand-800 to-brand-600 bg-clip-text text-2xl font-bold tracking-tight text-transparent sm:text-[1.85rem]">
              {greeting}, {user.first_name}
            </h1>
            <p className="mt-1.5 max-w-xl text-sm text-brand-300">
              Prioritize approvals, track workforce health, and keep hiring moving.
            </p>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button className="w-fit shadow-md shadow-brand-600/25 transition hover:scale-[1.02] hover:shadow-lg hover:shadow-brand-600/30">
                <Plus className="size-4" />
                Create
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

        {error && (
          <div className="animate-dash-fade-in rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4 xl:gap-4">
          <KpiCard
            label="Total Employees"
            value={kpis?.total_employees ?? 0}
            hint="Across the organization"
            icon={<Users className="size-5" />}
            tint="green"
            delay={60}
          />
          <KpiCard
            label="Currently On Leave"
            value={kpis?.on_leave ?? 0}
            hint="Approved leave covering today"
            icon={<Plane className="size-5" />}
            tint="sky"
            delay={120}
          />
          <KpiCard
            label="In Onboarding"
            value={kpis?.onboarding ?? 0}
            hint="Active onboarding plans"
            icon={<GraduationCap className="size-5" />}
            tint="teal"
            delay={180}
          />
          <KpiCard
            label="Pending Leave"
            value={kpis?.pending_leave ?? 0}
            hint="Awaiting approval"
            icon={<ClipboardList className="size-5" />}
            tint="amber"
            delay={240}
          />
        </div>

        <Card
          className={cn(
            "dash-card-lift animate-dash-fade-up overflow-hidden border-0 bg-white/90 shadow-md backdrop-blur",
            attentionItems.length > 0 && "dash-gradient-border"
          )}
          style={{ animationDelay: "280ms" }}
        >
          <div className="h-1 w-full bg-gradient-to-r from-amber-400 via-orange-400 to-rose-400" />
          <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
            <div>
              <CardTitle className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
                  <AlertCircle className="size-4" />
                </span>
                Needs Attention
              </CardTitle>
              <CardDescription>
                Highest-priority items that need a decision or follow-up.
              </CardDescription>
            </div>
            <Badge
              variant="warning"
              className={cn(attentionItems.length > 0 && "animate-dash-pulse-soft")}
            >
              {attentionItems.length}
            </Badge>
          </CardHeader>
          <CardContent>
            {attentionItems.length === 0 ? (
              <EmptyState message="Nothing urgent right now." />
            ) : (
              <ul className="divide-y divide-brand-100/80">
                {attentionItems.map((item, index) => (
                  <li
                    key={item.key}
                    className="animate-dash-fade-up"
                    style={{ animationDelay: `${320 + index * 45}ms` }}
                  >
                    <Link
                      href={item.href}
                      className="group -mx-2 flex items-center gap-3 rounded-xl px-2 py-3 transition hover:bg-gradient-to-r hover:from-amber-50/80 hover:to-transparent"
                    >
                      <span
                        className={cn(
                          "h-10 w-1 shrink-0 rounded-full transition group-hover:scale-y-110",
                          item.tone === "warning" && "bg-amber-400",
                          item.tone === "info" && "bg-sky-400",
                          item.tone === "danger" && "bg-rose-400"
                        )}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="truncate text-sm font-semibold text-brand-900">
                            {item.title}
                          </p>
                          <Badge
                            variant={
                              item.tone === "warning"
                                ? "warning"
                                : item.tone === "info"
                                  ? "info"
                                  : "danger"
                            }
                          >
                            {item.badge}
                          </Badge>
                        </div>
                        <p className="mt-0.5 truncate text-xs text-brand-300">
                          {item.meta}
                        </p>
                      </div>
                      <ChevronRight className="size-4 shrink-0 text-brand-300 transition group-hover:translate-x-0.5 group-hover:text-brand-600" />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <ChartCard
            title="Workforce Overview"
            description="Employees by department"
            empty={workforceChart.length === 0}
            accent="from-brand-600 to-sky-400"
            delay={360}
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-[1fr_1.1fr] sm:items-center">
              <div className="relative mx-auto h-52 w-full max-w-[220px]">
                <div className="absolute inset-6 rounded-full bg-gradient-to-br from-brand-500/10 to-sky-400/10 blur-xl" />
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={workforceChart}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={52}
                      outerRadius={78}
                      paddingAngle={3}
                      strokeWidth={0}
                      animationBegin={200}
                      animationDuration={900}
                    >
                      {workforceChart.map((entry, index) => (
                        <Cell
                          key={entry.name}
                          fill={WORKFORCE_COLORS[index % WORKFORCE_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number, name: string) => [
                        `${value} employees`,
                        name,
                      ]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="space-y-2.5">
                {workforceChart.map((row, index) => (
                  <li
                    key={row.name}
                    className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-sm transition hover:bg-brand-50/80 animate-dash-fade-up"
                    style={{ animationDelay: `${400 + index * 40}ms` }}
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <span
                        className="h-2.5 w-2.5 shrink-0 rounded-full ring-2 ring-white shadow"
                        style={{
                          backgroundColor:
                            WORKFORCE_COLORS[index % WORKFORCE_COLORS.length],
                        }}
                      />
                      <span className="truncate text-brand-900">{row.name}</span>
                    </div>
                    <span className="shrink-0 tabular-nums font-medium text-brand-700">
                      {row.value}
                      <span className="ml-1 font-normal text-brand-300">
                        · {row.percent}%
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </ChartCard>

          <ChartCard
            title="Leave Overview"
            description="Request counts by status"
            empty={leaveChart.length === 0}
            accent="from-emerald-500 to-amber-400"
            delay={420}
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-[1fr_1.1fr] sm:items-center">
              <div className="relative mx-auto h-52 w-full max-w-[220px]">
                <div className="absolute inset-6 rounded-full bg-gradient-to-br from-emerald-400/15 to-amber-300/15 blur-xl" />
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={leaveChart}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={52}
                      outerRadius={78}
                      paddingAngle={3}
                      strokeWidth={0}
                      animationBegin={280}
                      animationDuration={900}
                    >
                      {leaveChart.map((entry) => (
                        <Cell
                          key={entry.key}
                          fill={
                            LEAVE_COLORS[entry.key as keyof typeof LEAVE_COLORS]
                          }
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number, name: string) => [
                        `${value} requests`,
                        name,
                      ]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="space-y-2.5">
                {(
                  [
                    ["Approved", data?.leave_overview.approved ?? 0, "approved"],
                    ["Pending", data?.leave_overview.pending ?? 0, "pending"],
                    ["Rejected", data?.leave_overview.rejected ?? 0, "rejected"],
                  ] as const
                ).map(([label, value, key], index) => (
                  <li
                    key={key}
                    className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-sm transition hover:bg-brand-50/80 animate-dash-fade-up"
                    style={{ animationDelay: `${460 + index * 40}ms` }}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className="h-2.5 w-2.5 rounded-full ring-2 ring-white shadow"
                        style={{ backgroundColor: LEAVE_COLORS[key] }}
                      />
                      <span className="text-brand-900">{label}</span>
                    </div>
                    <span className="tabular-nums font-medium text-brand-700">
                      {value}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </ChartCard>
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Card
            className="dash-card-lift animate-dash-fade-up overflow-hidden border-0 bg-white/90 shadow-md backdrop-blur"
            style={{ animationDelay: "480ms" }}
          >
            <div className="h-1 w-full bg-gradient-to-r from-brand-600 to-teal-400" />
            <CardHeader>
              <CardTitle>Recent Hires</CardTitle>
              <CardDescription>Joined in the last 14 days</CardDescription>
            </CardHeader>
            <CardContent>
              {(data?.activity.recent_hires.length ?? 0) === 0 ? (
                <EmptyState message="No recent hires in this window." />
              ) : (
                <ul className="space-y-2">
                  {data!.activity.recent_hires.map((hire, index) => (
                    <li
                      key={hire.employee_id}
                      className="animate-dash-fade-up"
                      style={{ animationDelay: `${520 + index * 40}ms` }}
                    >
                      <Link
                        href={`/hr/employees/${hire.employee_id}`}
                        className="group flex items-center gap-3 rounded-xl p-2 transition hover:bg-gradient-to-r hover:from-emerald-50/80 hover:to-transparent"
                      >
                        <Avatar className="ring-2 ring-white shadow-md transition group-hover:scale-105">
                          <AvatarFallback
                            className={cn(
                              "bg-gradient-to-br text-white",
                              AVATAR_TONES[index % AVATAR_TONES.length]
                            )}
                          >
                            {initials(hire.employee_name)}
                          </AvatarFallback>
                        </Avatar>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-semibold text-brand-900">
                            {hire.employee_name}
                          </p>
                          <p className="truncate text-xs text-brand-300">
                            {[hire.position, hire.department]
                              .filter(Boolean)
                              .join(" · ") || "—"}
                          </p>
                        </div>
                        <span className="shrink-0 rounded-lg bg-brand-50 px-2 py-1 text-xs font-medium text-brand-700">
                          {formatDate(hire.hire_date)}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card
            className="dash-card-lift animate-dash-fade-up overflow-hidden border-0 bg-white/90 shadow-md backdrop-blur"
            style={{ animationDelay: "540ms" }}
          >
            <div className="h-1 w-full bg-gradient-to-r from-sky-500 to-brand-800" />
            <CardHeader>
              <CardTitle>Upcoming Activity</CardTitle>
              <CardDescription>
                Interviews, returns, and onboarding deadlines
              </CardDescription>
            </CardHeader>
            <CardContent>
              {upcomingActivity.length === 0 ? (
                <EmptyState message="No upcoming activity in the next 14 days." />
              ) : (
                <ul className="space-y-2">
                  {upcomingActivity.map((item, index) => (
                    <li
                      key={item.key}
                      className="animate-dash-fade-up"
                      style={{ animationDelay: `${580 + index * 40}ms` }}
                    >
                      <ActivityRow item={item} />
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        <Card
          className="dash-card-lift animate-dash-fade-up overflow-hidden border-0 bg-white/90 shadow-md backdrop-blur"
          style={{ animationDelay: "620ms" }}
        >
          <div className="h-1 w-full bg-gradient-to-r from-brand-800 via-brand-600 to-sky-400" />
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>Jump into common HR workflows</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-5">
              <ActionLink
                href="/hr/employees/create"
                icon={<UserPlus />}
                label="Add Employee"
                tint="green"
              />
              <ActionLink
                href="/hr/jobs/create"
                icon={<Briefcase />}
                label="Create Job"
                tint="navy"
              />
              <ActionLink
                href="/hr/jobs"
                icon={<ClipboardList />}
                label="Review Applications"
                tint="sky"
              />
              <ActionLink
                href="/hr/leave"
                icon={<CalendarDays />}
                label="Review Leave"
                tint="amber"
              />
              <ActionLink
                href="/hr/onboarding"
                icon={<GraduationCap />}
                label="Manage Onboarding"
                tint="teal"
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function KpiCard({
  label,
  value,
  hint,
  icon,
  tint,
  delay = 0,
}: {
  label: string;
  value: number;
  hint: string;
  icon: ReactNode;
  tint: "green" | "sky" | "amber" | "teal";
  delay?: number;
}) {
  const display = useCountUp(value);
  const styles = {
    green: {
      bar: "from-brand-600 to-emerald-400",
      icon: "bg-gradient-to-br from-emerald-50 to-emerald-100 text-emerald-700 shadow-emerald-200/60",
      glow: "from-emerald-400/20 to-transparent",
    },
    sky: {
      bar: "from-sky-500 to-cyan-400",
      icon: "bg-gradient-to-br from-sky-50 to-sky-100 text-sky-700 shadow-sky-200/60",
      glow: "from-sky-400/20 to-transparent",
    },
    amber: {
      bar: "from-amber-500 to-orange-400",
      icon: "bg-gradient-to-br from-amber-50 to-orange-100 text-amber-700 shadow-amber-200/60",
      glow: "from-amber-400/20 to-transparent",
    },
    teal: {
      bar: "from-teal-600 to-brand-500",
      icon: "bg-gradient-to-br from-teal-50 to-teal-100 text-teal-700 shadow-teal-200/60",
      glow: "from-teal-400/20 to-transparent",
    },
  }[tint];

  return (
    <Card
      className="dash-card-lift group relative animate-dash-fade-up overflow-hidden border-0 bg-white/90 shadow-md backdrop-blur"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className={cn("h-1 w-full bg-gradient-to-r", styles.bar)} />
      <div
        aria-hidden
        className={cn(
          "pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-gradient-to-br opacity-0 blur-2xl transition duration-500 group-hover:opacity-100",
          styles.glow
        )}
      />
      <CardContent className="relative p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-medium text-brand-300 sm:text-sm">{label}</p>
            <p className="mt-2 text-2xl font-bold tabular-nums tracking-tight text-brand-900 sm:text-3xl">
              {display}
            </p>
            <p className="mt-1 text-xs text-brand-300">{hint}</p>
          </div>
          <div
            className={cn(
              "flex h-11 w-11 items-center justify-center rounded-2xl shadow-inner transition duration-300 group-hover:-translate-y-0.5 group-hover:scale-105",
              styles.icon
            )}
          >
            {icon}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ChartCard({
  title,
  description,
  empty,
  children,
  accent,
  delay = 0,
}: {
  title: string;
  description: string;
  empty: boolean;
  children: ReactNode;
  accent: string;
  delay?: number;
}) {
  return (
    <Card
      className="dash-card-lift animate-dash-fade-up overflow-hidden border-0 bg-white/90 shadow-md backdrop-blur"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className={cn("h-1 w-full bg-gradient-to-r", accent)} />
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        {empty ? <EmptyState message="No data to chart yet." /> : children}
      </CardContent>
    </Card>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center animate-dash-fade-in">
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
        <CheckCircle2 className="size-5" />
      </div>
      <p className="text-sm text-brand-300">{message}</p>
    </div>
  );
}

function ActivityRow({ item }: { item: ActivityItem }) {
  const tone =
    item.kind === "interview"
      ? "bg-gradient-to-br from-sky-50 to-sky-100 text-sky-700"
      : item.kind === "leave"
        ? "bg-gradient-to-br from-emerald-50 to-teal-100 text-emerald-700"
        : "bg-gradient-to-br from-amber-50 to-orange-100 text-amber-700";

  const icon =
    item.kind === "interview" ? (
      <Briefcase className="size-4" />
    ) : item.kind === "leave" ? (
      <Plane className="size-4" />
    ) : (
      <Clock3 className="size-4" />
    );

  const content = (
    <div className="group flex items-center gap-3 rounded-xl p-2 transition hover:bg-gradient-to-r hover:from-sky-50/70 hover:to-transparent">
      <div
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl shadow-sm transition group-hover:scale-105",
          tone
        )}
      >
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-brand-900">{item.title}</p>
        <p className="truncate text-xs text-brand-300">{item.meta}</p>
      </div>
      <span className="shrink-0 rounded-lg bg-brand-50 px-2 py-1 text-xs font-medium text-brand-700">
        {item.when}
      </span>
    </div>
  );

  if (item.href) {
    return <Link href={item.href}>{content}</Link>;
  }
  return content;
}

function ActionLink({
  href,
  icon,
  label,
  tint,
}: {
  href: string;
  icon: ReactNode;
  label: string;
  tint: "green" | "navy" | "sky" | "amber" | "teal";
}) {
  const styles = {
    green: "hover:border-brand-500/40 hover:bg-emerald-50/80 text-brand-700",
    navy: "hover:border-brand-800/30 hover:bg-slate-50 text-brand-800",
    sky: "hover:border-sky-400/40 hover:bg-sky-50/80 text-sky-700",
    amber: "hover:border-amber-400/40 hover:bg-amber-50/80 text-amber-700",
    teal: "hover:border-teal-500/40 hover:bg-teal-50/80 text-teal-700",
  }[tint];

  return (
    <Link
      href={href}
      className={cn(
        "group inline-flex items-center gap-2.5 rounded-xl border border-brand-200/80 bg-gradient-to-br from-white to-brand-50/40 px-3 py-3.5 text-sm font-medium text-brand-900 shadow-sm transition duration-300 hover:-translate-y-0.5 hover:shadow-md",
        styles
      )}
    >
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-white shadow-sm transition group-hover:scale-110 [&_svg]:size-4">
        {icon}
      </span>
      <span className="leading-tight">{label}</span>
    </Link>
  );
}

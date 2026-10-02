"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ArrowRight,
  Building2,
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Eye,
  Funnel,
  Play,
  Plus,
  Search,
  Users,
} from "lucide-react";
import { OnboardingStatusBadge } from "@/components/OnboardingStatusBadge";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { Department } from "@/types/departments";
import type { Employee } from "@/types/employees";
import type { OnboardingListItem, OnboardingStatus } from "@/types/onboarding";
import { cn } from "@/lib/utils";

const card =
  "rounded-2xl border border-brand-200/70 bg-white shadow-[0_8px_24px_-18px_rgba(15,34,74,0.35)]";

const field =
  "h-10 w-full rounded-xl border border-[#0f224a]/25 bg-white px-3 text-sm text-[#0f224a] outline-none transition placeholder:text-[#0f224a]/40 focus:border-[#0f224a] focus:ring-2 focus:ring-[#0f224a]/15";

const PAGE_SIZE = 8;

const AVATAR_TONES = [
  "bg-brand-600",
  "bg-[#0f224a]",
  "bg-teal-600",
  "bg-sky-600",
  "bg-emerald-700",
  "bg-violet-600",
];

type EnrichedItem = OnboardingListItem & {
  department: string;
  email: string;
  progressPercent: number;
};

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function progressPercent(item: OnboardingListItem): number {
  if (item.total_tasks_count <= 0) {
    return item.status === "completed" ? 100 : 0;
  }
  return Math.round(
    (item.completed_tasks_count / item.total_tasks_count) * 100
  );
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

export default function OnboardingListPage() {
  const [items, setItems] = useState<OnboardingListItem[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<OnboardingStatus | "all">("all");
  const [department, setDepartment] = useState("all");
  const [startRange, setStartRange] = useState<"all" | "30d" | "month" | "year">(
    "all"
  );
  const [page, setPage] = useState(1);

  useEffect(() => {
    const load = async () => {
      setError("");
      setLoading(true);
      try {
        const [onboardings, employeeList, deps] = await Promise.all([
          api.listOnboardings(),
          api.listEmployees({ status: "all" }).catch(() => ({
            items: [] as Employee[],
            total: 0,
          })),
          api.listDepartments("all").catch(() => [] as Department[]),
        ]);
        setItems(onboardings);
        setEmployees(employeeList.items);
        setDepartments(deps);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load onboarding records"
        );
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const employeeById = useMemo(() => {
    const map = new Map<number, Employee>();
    for (const employee of employees) {
      map.set(employee.id, employee);
    }
    return map;
  }, [employees]);

  const enriched = useMemo((): EnrichedItem[] => {
    return items.map((item) => {
      const employee = employeeById.get(item.employee_id);
      return {
        ...item,
        department: employee?.department || "—",
        email: employee?.email || "",
        progressPercent: progressPercent(item),
      };
    });
  }, [items, employeeById]);

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();
    const now = new Date();

    return enriched.filter((item) => {
      if (status !== "all" && item.status !== status) return false;
      if (department !== "all" && item.department !== department) return false;

      if (startRange !== "all") {
        const started = new Date(item.started_at);
        if (Number.isNaN(started.getTime())) return false;
        if (startRange === "30d") {
          const cutoff = new Date(now);
          cutoff.setDate(cutoff.getDate() - 30);
          if (started < cutoff) return false;
        } else if (startRange === "month") {
          if (
            started.getFullYear() !== now.getFullYear() ||
            started.getMonth() !== now.getMonth()
          ) {
            return false;
          }
        } else if (startRange === "year") {
          if (started.getFullYear() !== now.getFullYear()) return false;
        }
      }

      if (!query) return true;
      const haystack = [
        item.employee_name,
        item.position,
        item.department,
        item.email,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [enriched, q, status, department, startRange]);

  useEffect(() => {
    setPage(1);
  }, [q, status, department, startRange]);

  const total = filtered.length;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, currentPage]);

  const rangeStart = total === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(currentPage * PAGE_SIZE, total);

  const inProgressCount = enriched.filter((i) => i.status === "in_progress").length;
  const completedCount = enriched.filter((i) => i.status === "completed").length;
  const onboardedIds = new Set(enriched.map((i) => i.employee_id));
  const notStartedCount = employees.filter(
    (employee) =>
      employee.employment_status === "active" && !onboardedIds.has(employee.id)
  ).length;

  const totalRecords = enriched.length || 1;
  const inProgressPct = Math.round((inProgressCount / totalRecords) * 100);
  const completedPct = Math.round((completedCount / totalRecords) * 100);

  const departmentOptions = useMemo(() => {
    const names = new Set<string>();
    for (const item of enriched) {
      if (item.department && item.department !== "—") names.add(item.department);
    }
    for (const dep of departments) {
      if (dep.status === "active") names.add(dep.name);
    }
    return Array.from(names).sort((a, b) => a.localeCompare(b));
  }, [enriched, departments]);

  const handleSearch = (event: FormEvent) => {
    event.preventDefault();
    setPage(1);
  };

  if (loading) {
    return (
      <div className="-m-6 flex min-h-[50vh] items-center justify-center bg-[#f3f6f5] p-6">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
      </div>
    );
  }

  return (
    <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 pb-8 sm:p-6">
      <div className="mx-auto max-w-[1200px] space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-brand-300">
              People
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-brand-900">
              Onboarding
            </h1>
            <p className="mt-1 text-[13px] text-brand-300">
              Track and manage the onboarding process for new employees.
            </p>
          </div>
          <Link
            href="/hr/onboarding/templates"
            className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700"
          >
            <Plus className="size-4" />
            Manage templates
          </Link>
        </div>

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {/* KPI cards */}
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
          <KpiCard
            label="Total onboardings"
            value={enriched.length}
            hint="Employees with an onboarding record"
            icon={<Users className="size-4" />}
            iconClass="bg-emerald-50 text-emerald-700"
            spark={[2, 3, 3, 4, 5, 4, 5]}
            sparkColor="#029870"
          />
          <KpiCard
            label="In progress"
            value={inProgressCount}
            hint={`${inProgressPct}% of total`}
            icon={<Play className="size-4" />}
            iconClass="bg-sky-50 text-sky-700"
            barPercent={inProgressPct}
            barClass="bg-sky-500"
          />
          <KpiCard
            label="Completed"
            value={completedCount}
            hint={`${completedPct}% of total`}
            icon={<CheckCircle2 className="size-4" />}
            iconClass="bg-emerald-50 text-emerald-700"
            barPercent={completedPct}
            barClass="bg-emerald-500"
          />
          <KpiCard
            label="Not started"
            value={notStartedCount}
            hint="Active employees without a record"
            icon={<Clock3 className="size-4" />}
            iconClass="bg-slate-100 text-slate-600"
            barPercent={
              employees.length
                ? Math.round((notStartedCount / employees.length) * 100)
                : 0
            }
            barClass="bg-slate-400"
          />
        </div>

        {/* Filters */}
        <form
          onSubmit={handleSearch}
          className={cn(
            card,
            "grid grid-cols-1 gap-3 p-3 sm:grid-cols-2 xl:grid-cols-4"
          )}
        >
          <label className="relative sm:col-span-2 xl:col-span-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#0f224a]/45" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search employee, position, or department..."
              className={cn(field, "pl-9")}
            />
          </label>
          <Select
            value={status}
            onValueChange={(next) =>
              setStatus(next as OnboardingStatus | "all")
            }
            aria-label="Filter by status"
            triggerClassName={field}
            options={[
              { value: "all", label: "All statuses" },
              { value: "in_progress", label: "In progress" },
              { value: "completed", label: "Completed" },
            ]}
          />
          <Select
            value={department}
            onValueChange={setDepartment}
            aria-label="Filter by department"
            triggerClassName={field}
            options={[
              { value: "all", label: "All departments" },
              ...departmentOptions.map((name) => ({
                value: name,
                label: name,
              })),
            ]}
          />
          <Select
            value={startRange}
            onValueChange={(next) =>
              setStartRange(next as "all" | "30d" | "month" | "year")
            }
            aria-label="Filter by start date"
            triggerClassName={field}
            options={[
              { value: "all", label: "Start date" },
              { value: "30d", label: "Last 30 days" },
              { value: "month", label: "This month" },
              { value: "year", label: "This year" },
            ]}
          />
        </form>

        <div className="flex items-center gap-2 text-[12px] text-brand-300">
          <Funnel className="size-3.5" />
          <span>
            Showing{" "}
            <span className="font-semibold text-brand-900">{total}</span>{" "}
            onboarding record{total === 1 ? "" : "s"}
          </span>
        </div>

        {/* Table */}
        <section className={cn(card, "overflow-hidden")}>
          {pageItems.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <p className="text-sm font-medium text-brand-900">
                No onboarding records found
              </p>
              <p className="mt-1 text-sm text-brand-300">
                Records are created automatically when a candidate is hired.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left">
                <thead>
                  <tr className="border-b border-brand-200/70 bg-[#f7faf9] text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
                    <th className="px-4 py-3">Employee</th>
                    <th className="px-4 py-3">Position</th>
                    <th className="px-4 py-3">Department</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Progress</th>
                    <th className="px-4 py-3">Started</th>
                    <th className="px-4 py-3">Tasks</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-brand-100">
                  {pageItems.map((item, index) => (
                    <tr
                      key={item.id}
                      className="transition hover:bg-[#f6f9f8]"
                    >
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-2.5">
                          <span
                            className={cn(
                              "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold text-white",
                              AVATAR_TONES[index % AVATAR_TONES.length]
                            )}
                          >
                            {initials(item.employee_name)}
                          </span>
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-brand-900">
                              {item.employee_name}
                            </p>
                            <p className="truncate text-[12px] text-brand-300">
                              {item.email || "—"}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-sm text-brand-700">
                        {item.position || "—"}
                      </td>
                      <td className="px-4 py-3.5 text-sm text-brand-700">
                        <span className="inline-flex items-center gap-1">
                          <Building2 className="size-3.5 text-brand-300" />
                          {item.department}
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        <OnboardingStatusBadge status={item.status} />
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="min-w-[7rem]">
                          <div className="mb-1 flex items-center justify-between gap-2">
                            <span className="text-[12px] font-semibold tabular-nums text-brand-900">
                              {item.progressPercent}%
                            </span>
                          </div>
                          <div className="h-1.5 overflow-hidden rounded-full bg-brand-100">
                            <div
                              className={cn(
                                "h-full rounded-full",
                                item.progressPercent >= 100
                                  ? "bg-emerald-500"
                                  : "bg-brand-600"
                              )}
                              style={{ width: `${item.progressPercent}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-sm text-brand-700">
                        <span className="inline-flex items-center gap-1.5">
                          <CalendarDays className="size-3.5 text-brand-300" />
                          {formatDate(item.started_at)}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-sm font-medium tabular-nums text-brand-900">
                        {item.completed_tasks_count}/{item.total_tasks_count}
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <Link
                          href={`/hr/onboarding/${item.id}`}
                          className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-brand-200 bg-white px-3 text-xs font-semibold text-brand-700 transition hover:bg-[#f3f6f5]"
                        >
                          <Eye className="size-3.5" />
                          View
                          <ArrowRight className="size-3.5" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {total > 0 ? (
            <div className="flex flex-col gap-3 border-t border-brand-200/70 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-[13px] text-brand-300">
                Showing {rangeStart} to {rangeEnd} of {total} employees
              </p>
              <div className="flex items-center gap-1.5">
                <PagerButton
                  disabled={currentPage <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  ariaLabel="Previous page"
                >
                  <ChevronLeft className="size-4" />
                </PagerButton>
                {Array.from({ length: pageCount }, (_, i) => i + 1)
                  .filter((n) => {
                    if (pageCount <= 5) return true;
                    return (
                      n === 1 ||
                      n === pageCount ||
                      Math.abs(n - currentPage) <= 1
                    );
                  })
                  .map((n, idx, arr) => {
                    const prev = arr[idx - 1];
                    return (
                      <span key={n} className="contents">
                        {prev != null && n - prev > 1 ? (
                          <span className="px-1 text-brand-300">…</span>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => setPage(n)}
                          className={cn(
                            "flex h-9 min-w-9 items-center justify-center rounded-lg px-2 text-sm font-semibold transition",
                            n === currentPage
                              ? "bg-brand-600 text-white"
                              : "text-brand-700 hover:bg-[#f3f6f5]"
                          )}
                        >
                          {n}
                        </button>
                      </span>
                    );
                  })}
                <PagerButton
                  disabled={currentPage >= pageCount}
                  onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
                  ariaLabel="Next page"
                >
                  <ChevronRight className="size-4" />
                </PagerButton>
              </div>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}

function KpiCard({
  label,
  value,
  hint,
  icon,
  iconClass,
  spark,
  sparkColor,
  barPercent,
  barClass,
}: {
  label: string;
  value: number;
  hint: string;
  icon: ReactNode;
  iconClass: string;
  spark?: number[];
  sparkColor?: string;
  barPercent?: number;
  barClass?: string;
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
        {spark ? (
          <MiniSpark points={spark} stroke={sparkColor} />
        ) : (
          <div className="w-16 pt-1">
            <div className="h-1.5 overflow-hidden rounded-full bg-brand-100">
              <div
                className={cn("h-full rounded-full", barClass)}
                style={{ width: `${Math.min(100, Math.max(0, barPercent ?? 0))}%` }}
              />
            </div>
          </div>
        )}
      </div>
      <p className="mt-3 text-2xl font-semibold tabular-nums tracking-tight text-brand-900">
        {value}
      </p>
      <p className="mt-0.5 text-[12px] font-medium text-brand-900">{label}</p>
      <p className="mt-0.5 text-[11px] text-brand-300">{hint}</p>
    </div>
  );
}

function PagerButton({
  children,
  disabled,
  onClick,
  ariaLabel,
}: {
  children: ReactNode;
  disabled: boolean;
  onClick: () => void;
  ariaLabel: string;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      aria-label={ariaLabel}
      className="flex h-9 w-9 items-center justify-center rounded-lg text-brand-700 transition hover:bg-[#f3f6f5] disabled:opacity-40"
    >
      {children}
    </button>
  );
}

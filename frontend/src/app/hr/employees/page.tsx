"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Funnel,
  MoreVertical,
  Plus,
  Search,
  TrendingUp,
  UserRound,
  Users,
  CalendarDays,
} from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { Department } from "@/types/departments";
import {
  EMPLOYMENT_TYPE_LABELS,
  type Employee,
  type EmploymentStatus,
} from "@/types/employees";
import { cn } from "@/lib/utils";

const card =
  "rounded-2xl border border-brand-200/70 bg-white shadow-[0_8px_24px_-18px_rgba(15,34,74,0.35)]";

const field =
  "h-10 w-full rounded-xl border border-[#0f224a]/25 bg-white px-3 text-sm text-[#0f224a] outline-none transition placeholder:text-[#0f224a]/40 focus:border-[#0f224a] focus:ring-2 focus:ring-[#0f224a]/15";

const PAGE_SIZE = 10;

const AVATAR_TONES = [
  "bg-brand-600",
  "bg-[#0f224a]",
  "bg-teal-600",
  "bg-sky-600",
  "bg-emerald-700",
];

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function isHireThisMonth(hireDate: string): boolean {
  const date = new Date(`${hireDate}T00:00:00`);
  if (Number.isNaN(date.getTime())) return false;
  const now = new Date();
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth()
  );
}

export default function EmployeesPage() {
  const [items, setItems] = useState<Employee[]>([]);
  const [total, setTotal] = useState(0);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<EmploymentStatus | "all">("active");
  const [departmentId, setDepartmentId] = useState<number | "">("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [stats, setStats] = useState({
    total: 0,
    active: 0,
    onLeave: 0,
    newThisMonth: 0,
  });

  const loadStats = async () => {
    try {
      const [dashboard, all] = await Promise.all([
        api.getHrDashboard(),
        api.listEmployees({ status: "all" }),
      ]);
      setStats({
        total: dashboard.kpis.total_employees,
        active: dashboard.kpis.active_employees,
        onLeave: dashboard.kpis.on_leave,
        newThisMonth: all.items.filter((employee) =>
          isHireThisMonth(employee.hire_date)
        ).length,
      });
    } catch {
      /* keep previous stats */
    }
  };

  const load = async (
    search = q,
    selectedStatus = status,
    selectedDepartment = departmentId
  ) => {
    setError("");
    setLoading(true);
    try {
      const result = await api.listEmployees({
        q: search || undefined,
        status: selectedStatus,
        department_id:
          selectedDepartment === "" ? undefined : Number(selectedDepartment),
      });
      setItems(result.items);
      setTotal(result.total);
      setPage(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load employees");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const bootstrap = async () => {
      try {
        setDepartments(await api.listDepartments("all"));
      } catch {
        setDepartments([]);
      }
      await Promise.all([load(), loadStats()]);
    };
    void bootstrap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearch = (event: FormEvent) => {
    event.preventDefault();
    void load();
  };

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return items.slice(start, start + PAGE_SIZE);
  }, [items, currentPage]);

  const rangeStart = total === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(currentPage * PAGE_SIZE, total);

  const subtitle =
    status === "all"
      ? `${total} employees`
      : status === "on_leave"
        ? `${total} on leave`
        : `${total} ${status} employees`;

  return (
    <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 pb-8 sm:p-6">
      <div className="mx-auto max-w-[1200px] space-y-5">
        {/* Header */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-brand-300">
              Employees
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-brand-900">
              Employees
            </h1>
            <p className="mt-1 text-[13px] text-brand-300">{subtitle}.</p>
          </div>
          <Link
            href="/hr/employees/create"
            className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700"
          >
            <Plus className="size-4" />
            Add employee
          </Link>
        </div>

        {/* KPI cards */}
        <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">
          <StatCard
            label="Total employees"
            value={stats.total}
            icon={<Users className="size-3.5" />}
            tone="bg-emerald-50 text-emerald-700"
          />
          <StatCard
            label="Active employees"
            value={stats.active}
            icon={<UserRound className="size-3.5" />}
            tone="bg-teal-50 text-teal-700"
          />
          <StatCard
            label="On leave today"
            value={stats.onLeave}
            icon={<CalendarDays className="size-3.5" />}
            tone="bg-amber-50 text-amber-700"
          />
          <StatCard
            label="New this month"
            value={stats.newThisMonth}
            icon={<TrendingUp className="size-3.5" />}
            tone="bg-sky-50 text-sky-700"
          />
        </div>

        {/* Filters */}
        <form
          onSubmit={handleSearch}
          className={cn(
            card,
            "grid grid-cols-1 gap-2.5 p-3 md:grid-cols-[1fr_180px_140px_auto] md:items-center"
          )}
        >
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-brand-300"
              aria-hidden
            />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search by name, email or employee number..."
              className={cn(field, "pl-10")}
            />
          </div>
          <Select
            value={departmentId === "" ? "" : String(departmentId)}
            onValueChange={(next) =>
              setDepartmentId(next ? Number(next) : "")
            }
            options={[
              { value: "", label: "All departments" },
              ...departments.map((department) => ({
                value: String(department.id),
                label: department.name,
              })),
            ]}
            triggerClassName={field}
            aria-label="Department"
          />
          <Select
            value={status}
            onValueChange={(next) =>
              setStatus(next as EmploymentStatus | "all")
            }
            options={[
              { value: "active", label: "Active" },
              { value: "inactive", label: "Inactive" },
              { value: "on_leave", label: "On leave" },
              { value: "all", label: "All statuses" },
            ]}
            triggerClassName={field}
            aria-label="Employment status"
          />
          <button
            type="submit"
            className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl bg-[#0f224a] px-4 text-sm font-semibold text-white transition hover:bg-[#16305f]"
          >
            <Funnel className="size-3.5" />
            Filter
          </button>
        </form>

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {/* Table */}
        <div className={cn(card, "overflow-hidden")}>
          {loading ? (
            <div className="flex justify-center py-16">
              <div className="h-7 w-7 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#f3f6f5] text-brand-600">
                <Users className="size-4" />
              </div>
              <p className="text-sm font-medium text-brand-900">No employees found</p>
              <p className="text-[13px] text-brand-300">
                Try another search or clear your filters.
              </p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="min-w-full">
                  <thead>
                    <tr className="border-b border-brand-200/80 bg-[#f7faf9]">
                      {[
                        "Employee",
                        "Department",
                        "Position",
                        "Employment type",
                        "Hire date",
                        "Status",
                        "Actions",
                      ].map((heading) => (
                        <th
                          key={heading}
                          className={cn(
                            "px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-[0.12em] text-brand-300",
                            heading === "Actions" && "text-right"
                          )}
                        >
                          {heading}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {pageItems.map((employee, index) => (
                      <tr
                        key={employee.id}
                        className="border-b border-brand-100 last:border-0 transition hover:bg-[#f7faf9]/80"
                      >
                        <td className="px-4 py-3">
                          <Link
                            href={`/hr/employees/${employee.id}`}
                            className="group flex items-center gap-3"
                          >
                            <Avatar className="h-9 w-9">
                              {employee.profile_picture_url ? (
                                <AvatarImage
                                  src={employee.profile_picture_url}
                                  alt=""
                                  className="object-cover"
                                />
                              ) : null}
                              <AvatarFallback
                                className={cn(
                                  "text-[10px] text-white",
                                  AVATAR_TONES[index % AVATAR_TONES.length]
                                )}
                              >
                                {initials(employee.full_name)}
                              </AvatarFallback>
                            </Avatar>
                            <div className="min-w-0">
                              <p className="truncate text-[13px] font-semibold text-brand-900 group-hover:text-brand-600">
                                {employee.full_name}
                              </p>
                              <p className="truncate text-[11px] text-brand-300">
                                {employee.employee_number}
                              </p>
                              <p className="truncate text-[11px] text-brand-300">
                                {employee.email}
                              </p>
                            </div>
                          </Link>
                        </td>
                        <td className="px-4 py-3 text-[13px] text-brand-700">
                          {employee.department || "—"}
                        </td>
                        <td className="px-4 py-3 text-[13px] text-brand-700">
                          {employee.position || "—"}
                        </td>
                        <td className="px-4 py-3 text-[13px] text-brand-700">
                          {EMPLOYMENT_TYPE_LABELS[employee.employment_type] ||
                            employee.employment_type}
                        </td>
                        <td className="px-4 py-3 text-[13px] tabular-nums text-brand-700">
                          {employee.hire_date}
                        </td>
                        <td className="px-4 py-3">
                          <StatusPill status={employee.employment_status} />
                        </td>
                        <td className="px-4 py-3 text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <button
                                type="button"
                                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-brand-300 transition hover:bg-[#f3f6f5] hover:text-brand-700"
                                aria-label={`Actions for ${employee.full_name}`}
                              >
                                <MoreVertical className="size-4" />
                              </button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem asChild>
                                <Link href={`/hr/employees/${employee.id}`}>
                                  View profile
                                </Link>
                              </DropdownMenuItem>
                              <DropdownMenuItem asChild>
                                <Link href={`/hr/employees/${employee.id}/edit`}>
                                  Edit employee
                                </Link>
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex flex-col gap-3 border-t border-brand-200/80 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-[13px] text-brand-300">
                  Showing{" "}
                  <span className="font-medium text-brand-700">{rangeStart}</span>{" "}
                  to{" "}
                  <span className="font-medium text-brand-700">{rangeEnd}</span>{" "}
                  of{" "}
                  <span className="font-medium text-brand-700">{total}</span>{" "}
                  employees
                </p>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    disabled={currentPage <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-brand-200 text-brand-600 transition hover:bg-[#f3f6f5] disabled:cursor-not-allowed disabled:opacity-40"
                    aria-label="Previous page"
                  >
                    <ChevronLeft className="size-4" />
                  </button>
                  {Array.from({ length: pageCount }, (_, i) => i + 1)
                    .slice(
                      Math.max(0, currentPage - 3),
                      Math.max(0, currentPage - 3) + Math.min(pageCount, 5)
                    )
                    .map((pageNumber) => (
                      <button
                        key={pageNumber}
                        type="button"
                        onClick={() => setPage(pageNumber)}
                        className={cn(
                          "inline-flex h-8 min-w-8 items-center justify-center rounded-lg px-2 text-[13px] font-semibold transition",
                          pageNumber === currentPage
                            ? "bg-brand-600 text-white"
                            : "border border-brand-200 text-brand-700 hover:bg-[#f3f6f5]"
                        )}
                      >
                        {pageNumber}
                      </button>
                    ))}
                  <button
                    type="button"
                    disabled={currentPage >= pageCount}
                    onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-brand-200 text-brand-600 transition hover:bg-[#f3f6f5] disabled:cursor-not-allowed disabled:opacity-40"
                    aria-label="Next page"
                  >
                    <ChevronRight className="size-4" />
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
  tone,
}: {
  label: string;
  value: number;
  icon: ReactNode;
  tone: string;
}) {
  return (
    <div className={cn(card, "flex items-center gap-2.5 px-3 py-2")}>
      <div
        className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
          tone
        )}
      >
        {icon}
      </div>
      <div className="min-w-0 leading-tight">
        <p className="text-base font-semibold tabular-nums tracking-tight text-brand-900">
          {value}
        </p>
        <p className="truncate text-[11px] text-brand-300">{label}</p>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const config: Record<string, { label: string; className: string; dot: string }> = {
    active: {
      label: "Active",
      className: "bg-emerald-50 text-emerald-800",
      dot: "bg-emerald-500",
    },
    inactive: {
      label: "Inactive",
      className: "bg-slate-100 text-slate-700",
      dot: "bg-slate-400",
    },
    on_leave: {
      label: "On leave",
      className: "bg-sky-50 text-sky-800",
      dot: "bg-sky-500",
    },
  };
  const style = config[status] || {
    label: status,
    className: "bg-slate-100 text-slate-700",
    dot: "bg-slate-400",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold",
        style.className
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", style.dot)} />
      {style.label}
    </span>
  );
}

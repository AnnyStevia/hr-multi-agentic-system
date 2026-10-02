"use client";

import { FormEvent, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  AlertCircle,
  Building2,
  ChevronLeft,
  ChevronRight,
  FolderKanban,
  MoreVertical,
  Network,
  Plus,
  Search,
  Users,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { Department, DepartmentStatus } from "@/types/departments";
import { cn } from "@/lib/utils";

const card =
  "rounded-2xl border border-brand-200/70 bg-white shadow-[0_8px_24px_-18px_rgba(15,34,74,0.35)]";

const field =
  "h-10 w-full rounded-xl border border-[#0f224a]/25 bg-white px-3 text-sm text-[#0f224a] outline-none transition placeholder:text-[#0f224a]/40 focus:border-[#0f224a] focus:ring-2 focus:ring-[#0f224a]/15";

const PAGE_SIZE = 8;

const ICON_TONES = [
  { bg: "bg-teal-50", text: "text-teal-700" },
  { bg: "bg-sky-50", text: "text-sky-700" },
  { bg: "bg-amber-50", text: "text-amber-700" },
  { bg: "bg-violet-50", text: "text-violet-700" },
  { bg: "bg-emerald-50", text: "text-emerald-700" },
  { bg: "bg-rose-50", text: "text-rose-700" },
];

type SortKey = "name_asc" | "name_desc" | "employees_desc" | "jobs_desc";

type DepartmentRow = Department & {
  employeeCount: number;
  jobCount: number;
  description: string;
};

function departmentDescription(name: string): string {
  const key = name.trim().toLowerCase();
  if (/\b(human resources|people|hr)\b/.test(key)) {
    return "Manages talent acquisition and employee relations";
  }
  if (/\b(it|tech|technology|engineering|software)\b/.test(key)) {
    return "Builds and supports digital products and infrastructure";
  }
  if (/\bmarket/.test(key)) {
    return "Drives brand, campaigns and growth initiatives";
  }
  if (/\b(pmo|project)\b/.test(key)) {
    return "Coordinates cross-functional delivery and governance";
  }
  if (/\b(finance|account)\b/.test(key)) {
    return "Oversees budgeting, payroll and financial controls";
  }
  if (/\b(sales|commercial)\b/.test(key)) {
    return "Owns revenue growth and client relationships";
  }
  if (/\b(legal|compliance)\b/.test(key)) {
    return "Guides policy, contracts and regulatory compliance";
  }
  if (/\b(ops|operations)\b/.test(key)) {
    return "Runs day-to-day operations and process excellence";
  }
  return "Organizational unit used across employees and job offers";
}

export default function DepartmentsPage() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [employeeCounts, setEmployeeCounts] = useState<Record<number, number>>({});
  const [jobCounts, setJobCounts] = useState<Record<number, number>>({});
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<DepartmentStatus | "all">("all");
  const [sortBy, setSortBy] = useState<SortKey>("name_asc");
  const [page, setPage] = useState(1);
  const [name, setName] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [actingId, setActingId] = useState<number | null>(null);

  const load = async () => {
    setError("");
    setLoading(true);
    try {
      const [deps, employees, jobs] = await Promise.all([
        api.listDepartments("all"),
        api.listEmployees({ status: "all" }).catch(() => ({ items: [], total: 0 })),
        api.listJobs().catch(() => []),
      ]);
      setDepartments(deps);

      const nextEmployees: Record<number, number> = {};
      for (const employee of employees.items) {
        nextEmployees[employee.department_id] =
          (nextEmployees[employee.department_id] ?? 0) + 1;
      }
      setEmployeeCounts(nextEmployees);

      const nextJobs: Record<number, number> = {};
      for (const job of jobs) {
        if (job.department_id == null) continue;
        nextJobs[job.department_id] = (nextJobs[job.department_id] ?? 0) + 1;
      }
      setJobCounts(nextJobs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load departments");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const rows = useMemo<DepartmentRow[]>(
    () =>
      departments.map((department) => ({
        ...department,
        employeeCount: employeeCounts[department.id] ?? 0,
        jobCount: jobCounts[department.id] ?? 0,
        description: departmentDescription(department.name),
      })),
    [departments, employeeCounts, jobCounts]
  );

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let next = rows.filter((row) => {
      if (status !== "all" && row.status !== status) return false;
      if (!needle) return true;
      return (
        row.name.toLowerCase().includes(needle) ||
        row.description.toLowerCase().includes(needle)
      );
    });

    next = [...next].sort((a, b) => {
      if (sortBy === "name_desc") return b.name.localeCompare(a.name);
      if (sortBy === "employees_desc") {
        return b.employeeCount - a.employeeCount || a.name.localeCompare(b.name);
      }
      if (sortBy === "jobs_desc") {
        return b.jobCount - a.jobCount || a.name.localeCompare(b.name);
      }
      return a.name.localeCompare(b.name);
    });

    return next;
  }, [rows, q, status, sortBy]);

  useEffect(() => {
    setPage(1);
  }, [q, status, sortBy]);

  const total = filtered.length;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, currentPage]);

  const rangeStart = total === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(currentPage * PAGE_SIZE, total);

  const activeCount = rows.filter((row) => row.status === "active").length;
  const inactiveCount = rows.filter((row) => row.status === "inactive").length;
  const activePct =
    rows.length === 0 ? 0 : Math.round((activeCount / rows.length) * 100);
  const inactivePct =
    rows.length === 0 ? 0 : Math.round((inactiveCount / rows.length) * 100);
  const topDepartment = useMemo(() => {
    if (rows.length === 0) return null;
    return [...rows].sort(
      (a, b) => b.employeeCount - a.employeeCount || a.name.localeCompare(b.name)
    )[0];
  }, [rows]);

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await api.createDepartment(name);
      setName("");
      setShowCreate(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create department");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeactivate = async (id: number) => {
    setActingId(id);
    setError("");
    try {
      await api.deactivateDepartment(id);
      await load();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to deactivate department"
      );
    } finally {
      setActingId(null);
    }
  };

  return (
    <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 pb-8 sm:p-6">
      <div className="mx-auto max-w-[1200px] space-y-5">
        {/* Header */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-brand-300">
              Organization
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-brand-900">
              Departments
            </h1>
            <p className="mt-1 text-[13px] text-brand-300">
              Manage organizational departments used across employees and job
              offers.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowCreate((value) => !value)}
            className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700"
          >
            <Plus className="size-4" />
            Add department
          </button>
        </div>

        {/* KPI cards */}
        <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">
          <StatCard
            label="Total departments"
            value={String(rows.length)}
            icon={<FolderKanban className="size-3.5" />}
            tone="bg-emerald-50 text-emerald-700"
          />
          <StatCard
            label="Active departments"
            value={`${activeCount}`}
            hint={`${activePct}%`}
            icon={<Users className="size-3.5" />}
            tone="bg-teal-50 text-teal-700"
          />
          <StatCard
            label="Inactive departments"
            value={`${inactiveCount}`}
            hint={`${inactivePct}%`}
            icon={<AlertCircle className="size-3.5" />}
            tone="bg-rose-50 text-rose-700"
          />
          <StatCard
            label="Most employees"
            value={topDepartment?.name ?? "—"}
            hint={
              topDepartment
                ? `${topDepartment.employeeCount} employee${
                    topDepartment.employeeCount === 1 ? "" : "s"
                  }`
                : undefined
            }
            icon={<Network className="size-3.5" />}
            tone="bg-sky-50 text-sky-700"
            valueClassName="text-sm"
          />
        </div>

        {showCreate ? (
          <form
            onSubmit={handleCreate}
            className={cn(card, "flex flex-col gap-3 p-4 sm:flex-row sm:items-center")}
          >
            <input
              required
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Department name"
              className={cn(field, "sm:flex-1")}
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowCreate(false);
                  setName("");
                }}
                className="inline-flex h-10 items-center justify-center rounded-xl border border-brand-200 px-4 text-sm font-medium text-brand-700 transition hover:bg-[#f3f6f5]"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex h-10 items-center justify-center rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:opacity-50"
              >
                {submitting ? "Adding..." : "Create"}
              </button>
            </div>
          </form>
        ) : null}

        {/* Filters */}
        <div
          className={cn(
            card,
            "grid grid-cols-1 gap-2.5 p-3 md:grid-cols-[1fr_180px_180px] md:items-center"
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
              placeholder="Search departments..."
              className={cn(field, "pl-10")}
            />
          </div>
          <Select
            value={status}
            onValueChange={(next) => setStatus(next as DepartmentStatus | "all")}
            options={[
              { value: "all", label: "All departments" },
              { value: "active", label: "Active" },
              { value: "inactive", label: "Inactive" },
            ]}
            triggerClassName={field}
            aria-label="Status"
          />
          <Select
            value={sortBy}
            onValueChange={(next) => setSortBy(next as SortKey)}
            options={[
              { value: "name_asc", label: "Name (A-Z)" },
              { value: "name_desc", label: "Name (Z-A)" },
              { value: "employees_desc", label: "Most employees" },
              { value: "jobs_desc", label: "Most job offers" },
            ]}
            triggerClassName={field}
            aria-label="Sort by"
          />
        </div>

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
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#f3f6f5] text-brand-600">
                <Building2 className="size-4" />
              </div>
              <p className="text-sm font-medium text-brand-900">No departments found</p>
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
                        "Name",
                        "Description",
                        "Employees",
                        "Job offers",
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
                    {pageItems.map((department, index) => {
                      const tone =
                        ICON_TONES[(department.id + index) % ICON_TONES.length];
                      return (
                        <tr
                          key={department.id}
                          className="border-b border-brand-200/60 last:border-0"
                        >
                          <td className="px-4 py-3.5">
                            <div className="flex items-center gap-3">
                              <div
                                className={cn(
                                  "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
                                  tone.bg,
                                  tone.text
                                )}
                              >
                                <Building2 className="size-4" />
                              </div>
                              <span className="text-sm font-semibold text-brand-900">
                                {department.name}
                              </span>
                            </div>
                          </td>
                          <td className="max-w-[280px] px-4 py-3.5 text-[13px] text-brand-300">
                            <span className="line-clamp-2">
                              {department.description}
                            </span>
                          </td>
                          <td className="px-4 py-3.5 text-sm tabular-nums text-brand-900">
                            {department.employeeCount}
                          </td>
                          <td className="px-4 py-3.5 text-sm tabular-nums text-brand-900">
                            {department.jobCount}
                          </td>
                          <td className="px-4 py-3.5">
                            <StatusPill status={department.status} />
                          </td>
                          <td className="px-4 py-3.5 text-right">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <button
                                  type="button"
                                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-brand-300 transition hover:bg-[#f3f6f5] hover:text-brand-700"
                                  aria-label={`Actions for ${department.name}`}
                                >
                                  <MoreVertical className="size-4" />
                                </button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                {department.status === "active" ? (
                                  <DropdownMenuItem
                                    disabled={actingId === department.id}
                                    onSelect={() => {
                                      void handleDeactivate(department.id);
                                    }}
                                  >
                                    {actingId === department.id
                                      ? "Deactivating..."
                                      : "Deactivate"}
                                  </DropdownMenuItem>
                                ) : (
                                  <DropdownMenuItem disabled>
                                    Already inactive
                                  </DropdownMenuItem>
                                )}
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </td>
                        </tr>
                      );
                    })}
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
                  departments
                </p>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    disabled={currentPage <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-brand-200 text-brand-600 transition hover:bg-[#f3f6f5] disabled:cursor-not-allowed disabled:opacity-40"
                    aria-label="Previous page"
                  >
                    <ChevronLeft className="size-4" />
                  </button>
                  <span className="px-2 text-[13px] tabular-nums text-brand-700">
                    {currentPage} / {pageCount}
                  </span>
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
  hint,
  icon,
  tone,
  valueClassName,
}: {
  label: string;
  value: string;
  hint?: string;
  icon: ReactNode;
  tone: string;
  valueClassName?: string;
}) {
  return (
    <div className={cn(card, "flex items-center gap-2.5 px-3 py-2.5")}>
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          tone
        )}
      >
        {icon}
      </div>
      <div className="min-w-0 leading-tight">
        <p
          className={cn(
            "truncate font-semibold tracking-tight text-brand-900",
            valueClassName ?? "text-base tabular-nums"
          )}
        >
          {value}
          {hint ? (
            <span className="ml-1 text-[11px] font-medium text-brand-300">
              ({hint})
            </span>
          ) : null}
        </p>
        <p className="truncate text-[11px] text-brand-300">{label}</p>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: DepartmentStatus }) {
  const active = status === "active";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold",
        active ? "bg-emerald-50 text-emerald-800" : "bg-slate-100 text-slate-700"
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          active ? "bg-emerald-500" : "bg-slate-400"
        )}
      />
      {active ? "Active" : "Inactive"}
    </span>
  );
}

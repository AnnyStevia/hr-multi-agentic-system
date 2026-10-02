"use client";

import { FormEvent, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Briefcase,
  Building2,
  ChevronLeft,
  ChevronRight,
  Link2,
  MoreVertical,
  Plus,
  Search,
  Unlink,
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
import type { Department } from "@/types/departments";
import type { OrgPosition } from "@/types/organization";
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

type SortKey = "title_asc" | "title_desc" | "employees_desc" | "department_asc";

type PositionRow = OrgPosition & {
  employeeCount: number;
};

export default function PositionsPage() {
  const [positions, setPositions] = useState<OrgPosition[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [employeeCounts, setEmployeeCounts] = useState<Record<number, number>>({});
  const [q, setQ] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState<number | "all" | "none">("all");
  const [sortBy, setSortBy] = useState<SortKey>("title_asc");
  const [page, setPage] = useState(1);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [departmentId, setDepartmentId] = useState<number | "">("");
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [actingId, setActingId] = useState<number | null>(null);

  const load = async () => {
    setError("");
    setLoading(true);
    try {
      const [pos, deps, employees] = await Promise.all([
        api.listPositions(),
        api.listDepartments("all"),
        api.listEmployees({ status: "all" }).catch(() => ({ items: [], total: 0 })),
      ]);
      setPositions(pos);
      setDepartments(deps);

      const nextEmployees: Record<number, number> = {};
      for (const employee of employees.items) {
        if (employee.position_id == null) continue;
        nextEmployees[employee.position_id] =
          (nextEmployees[employee.position_id] ?? 0) + 1;
      }
      setEmployeeCounts(nextEmployees);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load positions");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const rows = useMemo<PositionRow[]>(
    () =>
      positions.map((position) => ({
        ...position,
        employeeCount: employeeCounts[position.id] ?? 0,
      })),
    [positions, employeeCounts]
  );

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let next = rows.filter((row) => {
      if (departmentFilter === "none" && row.department_id != null) return false;
      if (
        typeof departmentFilter === "number" &&
        row.department_id !== departmentFilter
      ) {
        return false;
      }
      if (!needle) return true;
      return (
        row.title.toLowerCase().includes(needle) ||
        (row.description ?? "").toLowerCase().includes(needle) ||
        (row.department ?? "").toLowerCase().includes(needle)
      );
    });

    next = [...next].sort((a, b) => {
      if (sortBy === "title_desc") return b.title.localeCompare(a.title);
      if (sortBy === "employees_desc") {
        return b.employeeCount - a.employeeCount || a.title.localeCompare(b.title);
      }
      if (sortBy === "department_asc") {
        const left = a.department ?? "";
        const right = b.department ?? "";
        return left.localeCompare(right) || a.title.localeCompare(b.title);
      }
      return a.title.localeCompare(b.title);
    });

    return next;
  }, [rows, q, departmentFilter, sortBy]);

  useEffect(() => {
    setPage(1);
  }, [q, departmentFilter, sortBy]);

  const total = filtered.length;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, currentPage]);

  const rangeStart = total === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(currentPage * PAGE_SIZE, total);

  const linkedCount = rows.filter((row) => row.department_id != null).length;
  const unassignedCount = rows.filter((row) => row.department_id == null).length;
  const linkedPct =
    rows.length === 0 ? 0 : Math.round((linkedCount / rows.length) * 100);
  const topPosition = useMemo(() => {
    if (rows.length === 0) return null;
    return [...rows].sort(
      (a, b) => b.employeeCount - a.employeeCount || a.title.localeCompare(b.title)
    )[0];
  }, [rows]);

  const activeDepartments = useMemo(
    () => departments.filter((department) => department.status === "active"),
    [departments]
  );

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await api.createPosition({
        title,
        description: description.trim() || null,
        department_id: departmentId === "" ? null : Number(departmentId),
      });
      setTitle("");
      setDescription("");
      setDepartmentId("");
      setShowCreate(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create position");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    setActingId(id);
    setError("");
    try {
      await api.deletePosition(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete position");
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
              Positions
            </h1>
            <p className="mt-1 text-[13px] text-brand-300">
              Company-specific organizational titles used across employees and
              hiring.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowCreate((value) => !value)}
            className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700"
          >
            <Plus className="size-4" />
            Add position
          </button>
        </div>

        {/* KPI cards */}
        <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">
          <StatCard
            label="Total positions"
            value={String(rows.length)}
            icon={<Briefcase className="size-3.5" />}
            tone="bg-emerald-50 text-emerald-700"
          />
          <StatCard
            label="Linked to department"
            value={`${linkedCount}`}
            hint={`${linkedPct}%`}
            icon={<Link2 className="size-3.5" />}
            tone="bg-teal-50 text-teal-700"
          />
          <StatCard
            label="Unassigned"
            value={`${unassignedCount}`}
            icon={<Unlink className="size-3.5" />}
            tone="bg-amber-50 text-amber-700"
          />
          <StatCard
            label="Most employees"
            value={topPosition?.title ?? "—"}
            hint={
              topPosition
                ? `${topPosition.employeeCount} employee${
                    topPosition.employeeCount === 1 ? "" : "s"
                  }`
                : undefined
            }
            icon={<Users className="size-3.5" />}
            tone="bg-sky-50 text-sky-700"
            valueClassName="text-sm"
          />
        </div>

        {showCreate ? (
          <form onSubmit={handleCreate} className={cn(card, "space-y-3 p-4")}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <input
                required
                autoFocus
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Position title"
                className={field}
              />
              <Select
                value={departmentId === "" ? "" : String(departmentId)}
                onValueChange={(next) =>
                  setDepartmentId(next ? Number(next) : "")
                }
                triggerClassName={field}
                options={[
                  { value: "", label: "No department" },
                  ...activeDepartments.map((department) => ({
                    value: String(department.id),
                    label: department.name,
                  })),
                ]}
                aria-label="Department"
              />
            </div>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description (optional)"
              rows={2}
              className="w-full rounded-xl border border-[#0f224a]/25 bg-white px-3 py-2.5 text-sm text-[#0f224a] outline-none transition placeholder:text-[#0f224a]/40 focus:border-[#0f224a] focus:ring-2 focus:ring-[#0f224a]/15"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowCreate(false);
                  setTitle("");
                  setDescription("");
                  setDepartmentId("");
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
            "grid grid-cols-1 gap-2.5 p-3 md:grid-cols-[1fr_200px_180px] md:items-center"
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
              placeholder="Search positions..."
              className={cn(field, "pl-10")}
            />
          </div>
          <Select
            value={
              departmentFilter === "all" || departmentFilter === "none"
                ? departmentFilter
                : String(departmentFilter)
            }
            onValueChange={(next) => {
              if (next === "all" || next === "none") {
                setDepartmentFilter(next);
                return;
              }
              setDepartmentFilter(Number(next));
            }}
            options={[
              { value: "all", label: "All departments" },
              { value: "none", label: "No department" },
              ...departments.map((department) => ({
                value: String(department.id),
                label: department.name,
              })),
            ]}
            triggerClassName={field}
            aria-label="Department filter"
          />
          <Select
            value={sortBy}
            onValueChange={(next) => setSortBy(next as SortKey)}
            options={[
              { value: "title_asc", label: "Title (A-Z)" },
              { value: "title_desc", label: "Title (Z-A)" },
              { value: "department_asc", label: "Department (A-Z)" },
              { value: "employees_desc", label: "Most employees" },
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
                <Briefcase className="size-4" />
              </div>
              <p className="text-sm font-medium text-brand-900">No positions found</p>
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
                        "Title",
                        "Description",
                        "Department",
                        "Employees",
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
                    {pageItems.map((position, index) => {
                      const tone =
                        ICON_TONES[(position.id + index) % ICON_TONES.length];
                      return (
                        <tr
                          key={position.id}
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
                                <Briefcase className="size-4" />
                              </div>
                              <span className="text-sm font-semibold text-brand-900">
                                {position.title}
                              </span>
                            </div>
                          </td>
                          <td className="max-w-[280px] px-4 py-3.5 text-[13px] text-brand-300">
                            <span className="line-clamp-2">
                              {position.description?.trim() || "No description yet"}
                            </span>
                          </td>
                          <td className="px-4 py-3.5">
                            {position.department ? (
                              <span className="inline-flex items-center gap-1.5 text-sm text-brand-900">
                                <Building2 className="size-3.5 text-brand-300" />
                                {position.department}
                              </span>
                            ) : (
                              <span className="text-sm text-brand-300">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3.5 text-sm tabular-nums text-brand-900">
                            {position.employeeCount}
                          </td>
                          <td className="px-4 py-3.5 text-right">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <button
                                  type="button"
                                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-brand-300 transition hover:bg-[#f3f6f5] hover:text-brand-700"
                                  aria-label={`Actions for ${position.title}`}
                                >
                                  <MoreVertical className="size-4" />
                                </button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem
                                  disabled={actingId === position.id}
                                  onSelect={() => {
                                    void handleDelete(position.id);
                                  }}
                                >
                                  {actingId === position.id
                                    ? "Deleting..."
                                    : "Delete position"}
                                </DropdownMenuItem>
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
                  positions
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

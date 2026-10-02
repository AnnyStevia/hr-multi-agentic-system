"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  BarChart3,
  Briefcase,
  ChevronLeft,
  ChevronRight,
  Clock3,
  FileText,
  Funnel,
  MoreVertical,
  Plus,
  Search,
  Users,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { Department } from "@/types/departments";
import type { Job, JobStatus } from "@/types/jobs";
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

type SortKey =
  | "published_desc"
  | "published_asc"
  | "created_desc"
  | "title_asc"
  | "applications_desc";

type JobRow = Job & {
  applicationCount: number;
  newApplicationCount: number;
};

function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function jobCode(id: number): string {
  return `JO-${String(id).padStart(4, "0")}`;
}

function isThisMonth(value: string | null): boolean {
  if (!value) return false;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return false;
  const now = new Date();
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth()
  );
}

function isRecent(value: string, days = 7): boolean {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return false;
  const ageMs = Date.now() - date.getTime();
  return ageMs >= 0 && ageMs <= days * 24 * 60 * 60 * 1000;
}

function statusLabel(status: JobStatus): string {
  if (status === "published") return "Published";
  if (status === "closed") return "Closed";
  return "Draft";
}

export default function JobsListPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [applicationCounts, setApplicationCounts] = useState<
    Record<number, { total: number; recent: number }>
  >({});
  const [q, setQ] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState<number | "all" | "none">(
    "all"
  );
  const [status, setStatus] = useState<JobStatus | "all">("all");
  const [sortBy, setSortBy] = useState<SortKey>("published_desc");
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<number | null>(null);

  const load = async () => {
    setError("");
    setLoading(true);
    try {
      const [jobList, deps] = await Promise.all([
        api.listJobs(),
        api.listDepartments("all").catch(() => [] as Department[]),
      ]);
      setJobs(jobList);
      setDepartments(deps);

      const counts = await Promise.all(
        jobList.map(async (job) => {
          try {
            const apps = await api.listJobApplications(job.id);
            return {
              id: job.id,
              total: apps.length,
              recent: apps.filter((app) => isRecent(app.submitted_at)).length,
            };
          } catch {
            return { id: job.id, total: 0, recent: 0 };
          }
        })
      );

      const next: Record<number, { total: number; recent: number }> = {};
      for (const item of counts) {
        next[item.id] = { total: item.total, recent: item.recent };
      }
      setApplicationCounts(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const rows = useMemo<JobRow[]>(
    () =>
      jobs.map((job) => ({
        ...job,
        applicationCount: applicationCounts[job.id]?.total ?? 0,
        newApplicationCount: applicationCounts[job.id]?.recent ?? 0,
      })),
    [jobs, applicationCounts]
  );

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let next = rows.filter((row) => {
      if (status !== "all" && row.status !== status) return false;
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
        (row.department ?? "").toLowerCase().includes(needle) ||
        (row.location ?? "").toLowerCase().includes(needle) ||
        (row.position ?? "").toLowerCase().includes(needle) ||
        jobCode(row.id).toLowerCase().includes(needle)
      );
    });

    next = [...next].sort((a, b) => {
      if (sortBy === "title_asc") return a.title.localeCompare(b.title);
      if (sortBy === "applications_desc") {
        return (
          b.applicationCount - a.applicationCount || a.title.localeCompare(b.title)
        );
      }
      if (sortBy === "created_desc") {
        return (
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        );
      }
      if (sortBy === "published_asc") {
        const left = a.published_at ? new Date(a.published_at).getTime() : 0;
        const right = b.published_at ? new Date(b.published_at).getTime() : 0;
        return left - right || a.title.localeCompare(b.title);
      }
      const left = a.published_at ? new Date(a.published_at).getTime() : 0;
      const right = b.published_at ? new Date(b.published_at).getTime() : 0;
      return right - left || a.title.localeCompare(b.title);
    });

    return next;
  }, [rows, q, status, departmentFilter, sortBy]);

  useEffect(() => {
    setPage(1);
  }, [q, status, departmentFilter, sortBy]);

  const total = filtered.length;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, currentPage]);

  const rangeStart = total === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(currentPage * PAGE_SIZE, total);

  const publishedCount = rows.filter((row) => row.status === "published").length;
  const closedCount = rows.filter((row) => row.status === "closed").length;
  const draftCount = rows.filter((row) => row.status === "draft").length;
  const totalApplications = rows.reduce(
    (sum, row) => sum + row.applicationCount,
    0
  );
  const createdThisMonth = rows.filter((row) => isThisMonth(row.created_at)).length;

  const handleSearch = (event: FormEvent) => {
    event.preventDefault();
    setPage(1);
  };

  const handlePublish = async (id: number) => {
    setActingId(id);
    setError("");
    try {
      await api.publishJob(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to publish job");
    } finally {
      setActingId(null);
    }
  };

  const handleClose = async (id: number) => {
    setActingId(id);
    setError("");
    try {
      await api.closeJob(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to close job");
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
              Recruitment
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-brand-900">
              Job Offers
            </h1>
            <p className="mt-1 text-[13px] text-brand-300">
              Create, manage and track your job offers from draft to closed.
            </p>
          </div>
          <Link
            href="/hr/jobs/create"
            className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700"
          >
            <Plus className="size-4" />
            Create Job Offer
          </Link>
        </div>

        {/* KPI cards */}
        <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">
          <StatCard
            label="Total job offers"
            value={String(rows.length)}
            hint={
              createdThisMonth > 0
                ? `+${createdThisMonth} this month`
                : draftCount > 0
                  ? `${draftCount} draft`
                  : undefined
            }
            icon={<FileText className="size-3.5" />}
            tone="bg-emerald-50 text-emerald-700"
          />
          <StatCard
            label="Active job offers"
            value={String(publishedCount)}
            hint="Open and receiving applications"
            icon={<Users className="size-3.5" />}
            tone="bg-sky-50 text-sky-700"
          />
          <StatCard
            label="Closed job offers"
            value={String(closedCount)}
            hint="Successfully filled or cancelled"
            icon={<Clock3 className="size-3.5" />}
            tone="bg-amber-50 text-amber-700"
          />
          <StatCard
            label="Total applications"
            value={String(totalApplications)}
            hint="Across all job offers"
            icon={<BarChart3 className="size-3.5" />}
            tone="bg-violet-50 text-violet-700"
          />
        </div>

        {/* Filters */}
        <form
          onSubmit={handleSearch}
          className={cn(
            card,
            "grid grid-cols-1 gap-2.5 p-3 md:grid-cols-[1fr_170px_150px_180px_auto] md:items-center"
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
              placeholder="Search by title, department, or location..."
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
            aria-label="Department"
          />
          <Select
            value={status}
            onValueChange={(next) => setStatus(next as JobStatus | "all")}
            options={[
              { value: "all", label: "All statuses" },
              { value: "published", label: "Published" },
              { value: "draft", label: "Draft" },
              { value: "closed", label: "Closed" },
            ]}
            triggerClassName={field}
            aria-label="Status"
          />
          <Select
            value={sortBy}
            onValueChange={(next) => setSortBy(next as SortKey)}
            options={[
              { value: "published_desc", label: "Published date (newest)" },
              { value: "published_asc", label: "Published date (oldest)" },
              { value: "created_desc", label: "Created date (newest)" },
              { value: "title_asc", label: "Title (A-Z)" },
              { value: "applications_desc", label: "Most applications" },
            ]}
            triggerClassName={field}
            aria-label="Sort by"
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
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#f3f6f5] text-brand-600">
                <Briefcase className="size-4" />
              </div>
              <p className="text-sm font-medium text-brand-900">No job offers found</p>
              <p className="text-[13px] text-brand-300">
                Try another search or create a new job offer.
              </p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="min-w-full">
                  <thead>
                    <tr className="border-b border-brand-200/80 bg-[#f7faf9]">
                      {[
                        "Job title",
                        "Department",
                        "Location",
                        "Status",
                        "Applications",
                        "Created / Published",
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
                    {pageItems.map((job, index) => {
                      const tone =
                        ICON_TONES[(job.id + index) % ICON_TONES.length];
                      return (
                        <tr
                          key={job.id}
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
                              <div className="min-w-0">
                                <Link
                                  href={`/hr/jobs/${job.id}`}
                                  className="block truncate text-sm font-semibold text-brand-900 hover:text-brand-700"
                                >
                                  {job.title}
                                </Link>
                                <p className="text-[11px] text-brand-300">
                                  {jobCode(job.id)}
                                </p>
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-3.5 text-sm text-brand-900">
                            {job.department || "—"}
                          </td>
                          <td className="px-4 py-3.5 text-sm text-brand-900">
                            {job.location || "—"}
                          </td>
                          <td className="px-4 py-3.5">
                            <StatusPill status={job.status} />
                          </td>
                          <td className="px-4 py-3.5 text-sm text-brand-900">
                            <span className="font-medium tabular-nums">
                              {job.applicationCount}
                            </span>
                            {job.newApplicationCount > 0 ? (
                              <span className="text-brand-300">
                                {" "}
                                / {job.newApplicationCount} new
                              </span>
                            ) : null}
                          </td>
                          <td className="px-4 py-3.5 text-[13px] text-brand-300">
                            <div>{formatDate(job.created_at)}</div>
                            <div className="text-[11px]">
                              Pub. {formatDate(job.published_at)}
                            </div>
                          </td>
                          <td className="px-4 py-3.5">
                            <div className="flex items-center justify-end gap-1.5">
                              <Link
                                href={`/hr/jobs/${job.id}`}
                                className="inline-flex h-8 items-center rounded-lg border border-brand-200 px-2.5 text-xs font-semibold text-brand-700 transition hover:bg-[#f3f6f5]"
                              >
                                View
                              </Link>
                              <Link
                                href={`/hr/jobs/${job.id}/applications`}
                                className="inline-flex h-8 items-center rounded-lg border border-brand-200 px-2.5 text-xs font-semibold text-brand-700 transition hover:bg-[#f3f6f5]"
                              >
                                Applications
                              </Link>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <button
                                    type="button"
                                    className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-brand-300 transition hover:bg-[#f3f6f5] hover:text-brand-700"
                                    aria-label={`More actions for ${job.title}`}
                                  >
                                    <MoreVertical className="size-4" />
                                  </button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem asChild>
                                    <Link href={`/hr/jobs/${job.id}`}>
                                      Open details
                                    </Link>
                                  </DropdownMenuItem>
                                  <DropdownMenuItem asChild>
                                    <Link href={`/hr/jobs/${job.id}/applications`}>
                                      View applications
                                    </Link>
                                  </DropdownMenuItem>
                                  {(job.status === "draft" ||
                                    job.status === "published") && (
                                    <DropdownMenuSeparator />
                                  )}
                                  {job.status === "draft" ? (
                                    <DropdownMenuItem
                                      disabled={actingId === job.id}
                                      onSelect={() => {
                                        void handlePublish(job.id);
                                      }}
                                    >
                                      {actingId === job.id
                                        ? "Publishing..."
                                        : "Publish offer"}
                                    </DropdownMenuItem>
                                  ) : null}
                                  {job.status === "published" ? (
                                    <DropdownMenuItem
                                      disabled={actingId === job.id}
                                      onSelect={() => {
                                        void handleClose(job.id);
                                      }}
                                    >
                                      {actingId === job.id
                                        ? "Closing..."
                                        : "Close offer"}
                                    </DropdownMenuItem>
                                  ) : null}
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </div>
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
                  job offers
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
}: {
  label: string;
  value: string;
  hint?: string;
  icon: ReactNode;
  tone: string;
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
        <p className="truncate text-base font-semibold tabular-nums tracking-tight text-brand-900">
          {value}
        </p>
        <p className="truncate text-[11px] text-brand-300">{label}</p>
        {hint ? (
          <p className="truncate text-[10px] text-brand-300/80">{hint}</p>
        ) : null}
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: JobStatus }) {
  const styles =
    status === "published"
      ? { wrap: "bg-emerald-50 text-emerald-800", dot: "bg-emerald-500" }
      : status === "closed"
        ? { wrap: "bg-slate-100 text-slate-700", dot: "bg-slate-400" }
        : { wrap: "bg-amber-50 text-amber-800", dot: "bg-amber-500" };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold",
        styles.wrap
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", styles.dot)} />
      {statusLabel(status)}
    </span>
  );
}

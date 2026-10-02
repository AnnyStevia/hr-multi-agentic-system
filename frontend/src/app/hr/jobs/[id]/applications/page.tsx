"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState, type ReactNode } from "react";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  FileText,
  Funnel,
  MoreVertical,
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
import type { ApplicationListItem, ApplicationStatus } from "@/types/applications";
import type { Job, JobStatus } from "@/types/jobs";
import { cn } from "@/lib/utils";

const card =
  "rounded-2xl border border-brand-200/70 bg-white shadow-[0_8px_24px_-18px_rgba(15,34,74,0.35)]";

const field =
  "h-10 w-full rounded-xl border border-[#0f224a]/25 bg-white px-3 text-sm text-[#0f224a] outline-none transition placeholder:text-[#0f224a]/40 focus:border-[#0f224a] focus:ring-2 focus:ring-[#0f224a]/15";

const PAGE_SIZE = 8;

const STATUS_OPTIONS: Array<{ value: ApplicationStatus | "all"; label: string }> = [
  { value: "all", label: "All statuses" },
  { value: "submitted", label: "Submitted" },
  { value: "screening", label: "In review" },
  { value: "shortlisted", label: "Shortlisted" },
  { value: "rejected", label: "Rejected" },
  { value: "hired", label: "Hired" },
];

const STATUS_PILL: Record<
  ApplicationStatus,
  { wrap: string; dot: string; label: string }
> = {
  submitted: {
    wrap: "bg-slate-100 text-slate-700",
    dot: "bg-slate-400",
    label: "Submitted",
  },
  screening: {
    wrap: "bg-sky-50 text-sky-800",
    dot: "bg-sky-500",
    label: "In review",
  },
  shortlisted: {
    wrap: "bg-blue-50 text-blue-800",
    dot: "bg-blue-500",
    label: "Shortlisted",
  },
  rejected: {
    wrap: "bg-rose-50 text-rose-800",
    dot: "bg-rose-500",
    label: "Rejected",
  },
  hired: {
    wrap: "bg-emerald-50 text-emerald-800",
    dot: "bg-emerald-500",
    label: "Hired",
  },
};

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function jobStatusLabel(status: JobStatus): string {
  if (status === "published") return "Published";
  if (status === "closed") return "Closed";
  return "Draft";
}

function fitRingColor(score: number): string {
  if (score < 30) return "#dc2626"; // red
  if (score < 60) return "#f97316"; // orange (30–59)
  return "#16a34a"; // green (>= 60)
}

function initials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export default function JobApplicationsPage() {
  const params = useParams<{ id: string }>();
  const jobId = Number(params.id);
  const [job, setJob] = useState<Job | null>(null);
  const [applications, setApplications] = useState<ApplicationListItem[]>([]);
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState<ApplicationStatus | "all">("all");
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState<number | null>(null);

  const load = async () => {
    setError("");
    setLoading(true);
    try {
      const [jobData, rows] = await Promise.all([
        api.getJob(jobId),
        api.listJobApplications(jobId),
      ]);
      setJob(jobData);
      setApplications(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load applications");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!Number.isNaN(jobId)) {
      void load();
    }
  }, [jobId]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return applications.filter((app) => {
      if (statusFilter !== "all" && app.status !== statusFilter) return false;
      if (!needle) return true;
      return (
        app.candidate.full_name.toLowerCase().includes(needle) ||
        app.candidate.email.toLowerCase().includes(needle)
      );
    });
  }, [applications, q, statusFilter]);

  useEffect(() => {
    setPage(1);
  }, [q, statusFilter]);

  const total = filtered.length;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, currentPage]);

  const rangeStart = total === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(currentPage * PAGE_SIZE, total);

  const counts = useMemo(() => {
    const byStatus = {
      shortlisted: 0,
      screening: 0,
      submitted: 0,
      rejected: 0,
      hired: 0,
    };
    for (const app of applications) {
      byStatus[app.status] += 1;
    }
    return byStatus;
  }, [applications]);

  const allPageSelected =
    pageItems.length > 0 && pageItems.every((app) => selectedIds.includes(app.id));

  const toggleAllPage = () => {
    if (allPageSelected) {
      setSelectedIds((ids) =>
        ids.filter((id) => !pageItems.some((app) => app.id === id))
      );
      return;
    }
    setSelectedIds((ids) => {
      const next = new Set(ids);
      for (const app of pageItems) next.add(app.id);
      return Array.from(next);
    });
  };

  const toggleOne = (id: number) => {
    setSelectedIds((ids) =>
      ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id]
    );
  };

  const handleFilter = (event: FormEvent) => {
    event.preventDefault();
    setPage(1);
  };

  const changeStatus = async (applicationId: number, status: ApplicationStatus) => {
    setUpdatingId(applicationId);
    setError("");
    try {
      const updated = await api.updateApplicationStatus(applicationId, status);
      setApplications((rows) =>
        rows.map((row) =>
          row.id === applicationId ? { ...row, status: updated.status } : row
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update status");
    } finally {
      setUpdatingId(null);
    }
  };

  if (loading) {
    return (
      <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 sm:p-6">
        <div className="flex justify-center py-20">
          <div className="h-7 w-7 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
        </div>
      </div>
    );
  }

  const subtitle =
    [job?.department, job?.position, job?.location].filter(Boolean).join(" · ") ||
    "Candidates who applied to this offer";

  return (
    <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 pb-8 sm:p-6">
      <div className="mx-auto max-w-[1200px] space-y-5">
        <Link
          href={`/hr/jobs/${jobId}`}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-[#0f224a]/70 transition hover:text-[#0f224a]"
        >
          <ArrowLeft className="size-4" />
          Back to Job Offer
        </Link>

        {/* Header + KPI chips */}
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight text-brand-900">
                {job?.title || "Applications"}
              </h1>
              {job ? <JobStatusPill status={job.status} /> : null}
            </div>
            <p className="mt-1 text-[13px] text-brand-300">{subtitle}</p>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
            <KpiChip
              label="Total applications"
              value={applications.length}
              icon={<Users className="size-3.5" />}
            />
            <KpiChip
              label="Shortlisted"
              value={counts.shortlisted}
              dot="bg-emerald-500"
            />
            <KpiChip
              label="In review"
              value={counts.screening}
              dot="bg-sky-500"
            />
            <KpiChip
              label="Submitted"
              value={counts.submitted}
              dot="bg-amber-500"
            />
            <KpiChip
              label="Rejected"
              value={counts.rejected}
              dot="bg-rose-500"
            />
          </div>
        </div>

        {/* Filters */}
        <form
          onSubmit={handleFilter}
          className={cn(
            card,
            "grid grid-cols-1 gap-2.5 p-3 md:grid-cols-[1fr_180px_auto] md:items-center"
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
              placeholder="Search by candidate name or email..."
              className={cn(field, "pl-10")}
            />
          </div>
          <Select
            value={statusFilter}
            onValueChange={(next) =>
              setStatusFilter(next as ApplicationStatus | "all")
            }
            options={STATUS_OPTIONS}
            triggerClassName={field}
            aria-label="Status"
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
          {applications.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#f3f6f5] text-brand-600">
                <Users className="size-4" />
              </div>
              <p className="text-sm font-medium text-brand-900">No applications yet</p>
              <p className="text-[13px] text-brand-300">
                Candidates will appear here once they apply.
              </p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="py-16 text-center text-sm text-brand-300">
              No applications match your filters.
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="min-w-full">
                  <thead>
                    <tr className="border-b border-brand-200/80 bg-[#f7faf9]">
                      <th className="px-4 py-3 text-left">
                        <input
                          type="checkbox"
                          checked={allPageSelected}
                          onChange={toggleAllPage}
                          className="size-4 rounded border-brand-300 text-brand-600 focus:ring-brand-500/30"
                          aria-label="Select all on page"
                        />
                      </th>
                      {[
                        "Candidate",
                        "Email",
                        "Applied on",
                        "Status",
                        "Fit score",
                        "CV",
                        "Cover letter",
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
                    {pageItems.map((application) => {
                      const pill = STATUS_PILL[application.status];
                      return (
                        <tr
                          key={application.id}
                          className="border-b border-brand-200/60 last:border-0"
                        >
                          <td className="px-4 py-3.5">
                            <input
                              type="checkbox"
                              checked={selectedIds.includes(application.id)}
                              onChange={() => toggleOne(application.id)}
                              className="size-4 rounded border-brand-300 text-brand-600 focus:ring-brand-500/30"
                              aria-label={`Select ${application.candidate.full_name}`}
                            />
                          </td>
                          <td className="px-4 py-3.5">
                            <div className="flex items-center gap-3">
                              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#0f224a] text-[11px] font-semibold text-white">
                                {initials(application.candidate.full_name)}
                              </span>
                              <div className="min-w-0">
                                <p className="truncate text-sm font-semibold text-brand-900">
                                  {application.candidate.full_name}
                                </p>
                                <p className="text-[11px] text-brand-300">Candidate</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-3.5 text-sm text-brand-700">
                            {application.candidate.email}
                          </td>
                          <td className="px-4 py-3.5 text-[13px] whitespace-nowrap text-brand-300">
                            {formatDate(application.submitted_at)}
                          </td>
                          <td className="px-4 py-3.5">
                            <Select
                              value={application.status}
                              onValueChange={(next) => {
                                void changeStatus(
                                  application.id,
                                  next as ApplicationStatus
                                );
                              }}
                              disabled={updatingId === application.id}
                              options={STATUS_OPTIONS.filter(
                                (option) => option.value !== "all"
                              )}
                              triggerClassName={cn(
                                "h-8 w-[140px] rounded-full border-0 px-2.5 text-[11px] font-semibold shadow-none",
                                pill.wrap,
                                "hover:opacity-90 focus:ring-0"
                              )}
                              aria-label={`Status for ${application.candidate.full_name}`}
                            />
                          </td>
                          <td className="px-4 py-3.5">
                            <FitScoreRing score={application.fit_score} />
                          </td>
                          <td className="px-4 py-3.5">
                            {application.has_cv ? (
                              <Link
                                href={`/hr/applications/${application.id}#documents`}
                                className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-brand-200 px-2.5 text-xs font-semibold text-brand-700 transition hover:bg-[#f3f6f5]"
                              >
                                <FileText className="size-3.5" />
                                View
                              </Link>
                            ) : (
                              <span className="text-sm text-brand-300">No</span>
                            )}
                          </td>
                          <td className="px-4 py-3.5 text-sm text-brand-700">
                            {application.has_cover_letter ? "Yes" : "No"}
                          </td>
                          <td className="px-4 py-3.5 text-right">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <button
                                  type="button"
                                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-brand-300 transition hover:bg-[#f3f6f5] hover:text-brand-700"
                                  aria-label={`Actions for ${application.candidate.full_name}`}
                                >
                                  <MoreVertical className="size-4" />
                                </button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem asChild>
                                  <Link href={`/hr/applications/${application.id}`}>
                                    View application
                                  </Link>
                                </DropdownMenuItem>
                                {application.has_cv ? (
                                  <DropdownMenuItem asChild>
                                    <Link
                                      href={`/hr/applications/${application.id}#documents`}
                                    >
                                      Open CV
                                    </Link>
                                  </DropdownMenuItem>
                                ) : null}
                                <DropdownMenuItem asChild>
                                  <Link
                                    href={`/hr/applications/${application.id}/invite`}
                                  >
                                    Invite to interview
                                  </Link>
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
                  application{total === 1 ? "" : "s"}
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
                  <span className="inline-flex h-8 min-w-8 items-center justify-center rounded-lg bg-brand-600 px-2 text-[13px] font-semibold text-white">
                    {currentPage}
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

function FitScoreRing({ score }: { score?: number | null }) {
  if (score == null || Number.isNaN(score)) {
    return <span className="text-sm text-brand-300">—</span>;
  }

  const clamped = Math.max(0, Math.min(100, score));
  const color = fitRingColor(clamped);
  const size = 52;
  const stroke = 5;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
      title={`${clamped} / 100`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
        <span className="text-[12px] font-bold tabular-nums text-brand-900">
          {Math.round(clamped)}
        </span>
        <span className="text-[8px] font-medium text-brand-300">/ 100</span>
      </div>
    </div>
  );
}

function JobStatusPill({ status }: { status: JobStatus }) {
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
      {jobStatusLabel(status)}
    </span>
  );
}

function KpiChip({
  label,
  value,
  icon,
  dot,
}: {
  label: string;
  value: number;
  icon?: ReactNode;
  dot?: string;
}) {
  return (
    <div className={cn(card, "min-w-[110px] px-3 py-2")}>
      <div className="flex items-center gap-1.5">
        {icon ? <span className="text-brand-300">{icon}</span> : null}
        {dot ? <span className={cn("h-1.5 w-1.5 rounded-full", dot)} /> : null}
        <p className="text-base font-semibold tabular-nums text-brand-900">{value}</p>
      </div>
      <p className="mt-0.5 truncate text-[10px] text-brand-300">{label}</p>
    </div>
  );
}

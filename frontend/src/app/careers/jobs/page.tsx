"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ArrowRight,
  BarChart3,
  Briefcase,
  Building2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Code2,
  Funnel,
  MapPin,
  Megaphone,
  Monitor,
  Search,
} from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import { EMPLOYMENT_TYPE_LABELS } from "@/types/employees";
import type { ApplicationStatus } from "@/types/applications";
import type { EmploymentType, Job } from "@/types/jobs";
import { cn } from "@/lib/utils";

const card =
  "rounded-2xl border border-brand-200/70 bg-white shadow-[0_8px_24px_-18px_rgba(15,34,74,0.35)]";

const field =
  "h-10 w-full rounded-xl border border-[#0f224a]/25 bg-white px-3 text-sm text-[#0f224a] outline-none transition placeholder:text-[#0f224a]/40 focus:border-[#0f224a] focus:ring-2 focus:ring-[#0f224a]/15";

const PAGE_SIZE = 6;

const ICON_TONES = [
  { bg: "bg-violet-50", text: "text-violet-700", Icon: BarChart3 },
  { bg: "bg-amber-50", text: "text-amber-700", Icon: Megaphone },
  { bg: "bg-sky-50", text: "text-sky-700", Icon: Monitor },
  { bg: "bg-emerald-50", text: "text-emerald-700", Icon: Code2 },
  { bg: "bg-teal-50", text: "text-teal-700", Icon: Briefcase },
  { bg: "bg-rose-50", text: "text-rose-700", Icon: Building2 },
];

type SortKey = "newest" | "oldest" | "title";

function formatPosted(value: string | null): string {
  if (!value) return "Recently";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Recently";
  return date.toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function employmentTone(type: EmploymentType): string {
  if (type === "internship") return "bg-amber-50 text-amber-800";
  if (type === "contract") return "bg-sky-50 text-sky-800";
  if (type === "part_time") return "bg-violet-50 text-violet-800";
  return "bg-emerald-50 text-emerald-800";
}

function snippet(text: string, max = 110): string {
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  return `${clean.slice(0, max).trim()}…`;
}

export default function CareerJobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [statusByJobId, setStatusByJobId] = useState<
    Record<number, ApplicationStatus>
  >({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [location, setLocation] = useState("all");
  const [jobType, setJobType] = useState<"all" | EmploymentType>("all");
  const [department, setDepartment] = useState("all");
  const [sortBy, setSortBy] = useState<SortKey>("newest");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const load = async () => {
      setError("");
      setLoading(true);
      try {
        const published = await api.listCareerJobs();
        setJobs(published);
        try {
          const mine = await api.listMyApplications();
          const map: Record<number, ApplicationStatus> = {};
          for (const application of mine) {
            map[application.job_id] = application.status;
          }
          setStatusByJobId(map);
        } catch {
          setStatusByJobId({});
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load jobs");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const locations = useMemo(() => {
    const set = new Set<string>();
    for (const job of jobs) {
      if (job.location?.trim()) set.add(job.location.trim());
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [jobs]);

  const departments = useMemo(() => {
    const set = new Set<string>();
    for (const job of jobs) {
      if (job.department?.trim()) set.add(job.department.trim());
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [jobs]);

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();
    const next = jobs.filter((job) => {
      if (location !== "all" && (job.location || "").trim() !== location) {
        return false;
      }
      if (jobType !== "all" && job.employment_type !== jobType) return false;
      if (department !== "all" && (job.department || "").trim() !== department) {
        return false;
      }
      if (!query) return true;
      const haystack = [
        job.title,
        job.department,
        job.location,
        job.description,
        job.position,
        EMPLOYMENT_TYPE_LABELS[job.employment_type],
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });

    next.sort((a, b) => {
      if (sortBy === "title") return a.title.localeCompare(b.title);
      const left = a.published_at ? new Date(a.published_at).getTime() : 0;
      const right = b.published_at ? new Date(b.published_at).getTime() : 0;
      if (sortBy === "oldest") return left - right || a.title.localeCompare(b.title);
      return right - left || a.title.localeCompare(b.title);
    });

    return next;
  }, [jobs, q, location, jobType, department, sortBy]);

  useEffect(() => {
    setPage(1);
  }, [q, location, jobType, department, sortBy]);

  const total = filtered.length;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageItems = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, currentPage]);

  const rangeStart = total === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(currentPage * PAGE_SIZE, total);

  const handleSearch = (event: FormEvent) => {
    event.preventDefault();
    setPage(1);
  };

  return (
    <div className="min-h-full bg-[#f3f6f5] p-5 pb-8 sm:p-6">
      <div className="mx-auto max-w-[1100px] space-y-5">
        {/* Hero */}
        <section className="relative overflow-hidden rounded-2xl border border-brand-200/50 bg-white px-6 py-7 sm:px-8 sm:py-8">
          <div
            className="pointer-events-none absolute -right-8 top-0 h-40 w-64 opacity-50"
            aria-hidden
          >
            <svg viewBox="0 0 280 160" fill="none" className="h-full w-full">
              <path
                d="M0 90 C60 40, 120 140, 180 70 C220 30, 250 80, 280 50"
                stroke="#029870"
                strokeWidth="2.5"
                strokeLinecap="round"
                opacity="0.45"
              />
              <path
                d="M20 120 C80 70, 140 150, 200 90 C240 55, 260 100, 280 85"
                stroke="#0d9488"
                strokeWidth="2"
                strokeLinecap="round"
                opacity="0.3"
              />
            </svg>
          </div>
          <p className="relative text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-300">
            Join our team
          </p>
          <h1 className="relative mt-2 max-w-xl text-2xl font-semibold tracking-tight text-brand-900 sm:text-[1.85rem]">
            Find your next opportunity
          </h1>
          <p className="relative mt-2 max-w-lg text-sm text-brand-300">
            Explore our open positions and be part of a team that makes an impact.
          </p>
        </section>

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {/* Filters */}
        <form
          onSubmit={handleSearch}
          className={cn(card, "grid grid-cols-1 gap-3 p-3 sm:grid-cols-2 xl:grid-cols-4")}
        >
          <label className="relative sm:col-span-2 xl:col-span-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#0f224a]/45" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search jobs, keywords, or location..."
              className={cn(field, "pl-9")}
            />
          </label>
          <Select
            value={location}
            onValueChange={setLocation}
            aria-label="Filter by location"
            triggerClassName={field}
            options={[
              { value: "all", label: "All locations" },
              ...locations.map((item) => ({ value: item, label: item })),
            ]}
          />
          <Select
            value={jobType}
            onValueChange={(next) => setJobType(next as "all" | EmploymentType)}
            aria-label="Filter by job type"
            triggerClassName={field}
            options={[
              { value: "all", label: "All job types" },
              ...Object.entries(EMPLOYMENT_TYPE_LABELS).map(([value, label]) => ({
                value,
                label,
              })),
            ]}
          />
          <Select
            value={department}
            onValueChange={setDepartment}
            aria-label="Filter by department"
            triggerClassName={field}
            options={[
              { value: "all", label: "All departments" },
              ...departments.map((item) => ({ value: item, label: item })),
            ]}
          />
        </form>

        {/* Count + sort */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-brand-300">
            <span className="font-semibold text-brand-900">{total}</span> open
            position{total === 1 ? "" : "s"}
          </p>
          <div className="flex items-center gap-2">
            <Funnel className="size-3.5 text-brand-300" />
            <span className="text-[12px] font-medium text-brand-300">Sort by</span>
            <Select
              value={sortBy}
              onValueChange={(next) => setSortBy(next as SortKey)}
              aria-label="Sort jobs"
              triggerClassName="h-9 min-w-[10rem] rounded-xl border border-[#0f224a]/25 bg-white px-3 text-sm text-[#0f224a]"
              options={[
                { value: "newest", label: "Newest first" },
                { value: "oldest", label: "Oldest first" },
                { value: "title", label: "Title A–Z" },
              ]}
            />
          </div>
        </div>

        {/* Results */}
        {loading ? (
          <div className={cn(card, "flex justify-center py-16")}>
            <div className="h-7 w-7 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
          </div>
        ) : pageItems.length === 0 ? (
          <div className={cn(card, "px-6 py-16 text-center")}>
            <p className="text-sm font-medium text-brand-900">No matching openings</p>
            <p className="mt-1 text-sm text-brand-300">
              Try clearing filters or check back later.
            </p>
          </div>
        ) : (
          <ul className="space-y-3">
            {pageItems.map((job, index) => {
              const tone = ICON_TONES[index % ICON_TONES.length];
              const Icon = tone.Icon;
              const status = statusByJobId[job.id];
              return (
                <li key={job.id} className={cn(card, "p-4 sm:p-5")}>
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                    <div className="flex min-w-0 flex-1 gap-3.5">
                      <span
                        className={cn(
                          "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl",
                          tone.bg,
                          tone.text
                        )}
                      >
                        <Icon className="size-5" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h2 className="text-[15px] font-semibold text-brand-900">
                            {job.title}
                          </h2>
                          {status ? <StatusBadge status={status} /> : null}
                        </div>
                        <p className="mt-0.5 text-[13px] text-brand-300">
                          {job.department || job.position || "Open role"}
                        </p>
                        <p className="mt-2 line-clamp-2 text-[13px] leading-relaxed text-brand-700/80">
                          {snippet(job.description)}
                        </p>
                        <div className="mt-3 flex flex-wrap items-center gap-2">
                          <span
                            className={cn(
                              "inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold",
                              employmentTone(job.employment_type)
                            )}
                          >
                            {EMPLOYMENT_TYPE_LABELS[job.employment_type] ||
                              job.employment_type}
                          </span>
                          {job.location ? (
                            <span className="inline-flex items-center gap-1 text-[12px] text-brand-300">
                              <MapPin className="size-3.5" />
                              {job.location}
                            </span>
                          ) : null}
                        </div>
                      </div>
                    </div>

                    <div className="flex shrink-0 flex-col items-stretch gap-3 sm:flex-row sm:items-center lg:flex-col lg:items-end">
                      <span className="inline-flex items-center gap-1.5 text-[12px] text-brand-300 lg:justify-end">
                        <Clock3 className="size-3.5" />
                        Posted {formatPosted(job.published_at)}
                      </span>
                      <Link
                        href={`/careers/jobs/${job.id}`}
                        className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700"
                      >
                        View details
                        <ArrowRight className="size-4" />
                      </Link>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        {/* Pagination */}
        {!loading && total > 0 ? (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-[13px] text-brand-300">
              Showing {rangeStart} to {rangeEnd} of {total} jobs
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
                            : "text-brand-700 hover:bg-white"
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
      </div>
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
      className="flex h-9 w-9 items-center justify-center rounded-lg text-brand-700 transition hover:bg-white disabled:opacity-40"
    >
      {children}
    </button>
  );
}

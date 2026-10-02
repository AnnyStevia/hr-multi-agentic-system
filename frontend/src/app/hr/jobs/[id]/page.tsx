"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Briefcase,
  Building2,
  CalendarDays,
  CheckCircle2,
  CircleHelp,
  ClipboardList,
  Copy,
  FileText,
  Link2,
  ListChecks,
  MapPin,
  MoreVertical,
  Share2,
  Users,
  XCircle,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { api } from "@/lib/api";
import { EMPLOYMENT_TYPE_LABELS } from "@/types/employees";
import type { Job, JobStatus } from "@/types/jobs";
import { cn } from "@/lib/utils";

const card =
  "rounded-2xl border border-brand-200/70 bg-white shadow-[0_8px_24px_-18px_rgba(15,34,74,0.35)]";

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

function requirementLines(requirements: string | null): string[] {
  if (!requirements?.trim()) return [];
  return requirements
    .split(/\r?\n|•|;/)
    .map((line) => line.replace(/^[-*]\s*/, "").trim())
    .filter(Boolean);
}

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [job, setJob] = useState<Job | null>(null);
  const [applicationCount, setApplicationCount] = useState(0);
  const [newApplicationCount, setNewApplicationCount] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState<"publish" | "close" | "duplicate" | null>(
    null
  );

  const jobId = Number(params.id);

  useEffect(() => {
    const load = async () => {
      setError("");
      setLoading(true);
      try {
        const [jobData, apps] = await Promise.all([
          api.getJob(jobId),
          api.listJobApplications(jobId).catch(() => []),
        ]);
        setJob(jobData);
        setApplicationCount(apps.length);
        setNewApplicationCount(
          apps.filter((app) => isRecent(app.submitted_at)).length
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load job");
        setJob(null);
      } finally {
        setLoading(false);
      }
    };
    if (!Number.isNaN(jobId)) {
      void load();
    }
  }, [jobId]);

  const requirements = useMemo(
    () => requirementLines(job?.requirements ?? null),
    [job?.requirements]
  );

  const handlePublish = async () => {
    setActing("publish");
    setError("");
    setNotice("");
    try {
      setJob(await api.publishJob(jobId));
      setNotice("Job offer published.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to publish job");
    } finally {
      setActing(null);
    }
  };

  const handleClose = async () => {
    setActing("close");
    setError("");
    setNotice("");
    try {
      setJob(await api.closeJob(jobId));
      setNotice("Job offer closed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to close job");
    } finally {
      setActing(null);
    }
  };

  const handleDuplicate = async () => {
    if (!job) return;
    setActing("duplicate");
    setError("");
    setNotice("");
    try {
      const created = await api.createJob({
        title: `${job.title} (Copy)`,
        description: job.description,
        department_id: job.department_id ?? undefined,
        position: job.position ?? undefined,
        location: job.location ?? undefined,
        employment_type: job.employment_type,
        internship_duration_months: job.internship_duration_months ?? undefined,
        requirements: job.requirements ?? undefined,
        questions: job.questions?.map((question, index) => ({
          prompt: question.prompt,
          question_type: question.question_type,
          required: question.required,
          display_order: question.display_order ?? index,
        })),
      });
      router.push(`/hr/jobs/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to duplicate job");
      setActing(null);
    }
  };

  const handleShare = async () => {
    if (!job) return;
    const url = `${window.location.origin}/careers/jobs/${job.id}`;
    try {
      await navigator.clipboard.writeText(url);
      setNotice("Public job link copied to clipboard.");
      setError("");
    } catch {
      setError("Could not copy the share link.");
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

  if (!job) {
    return (
      <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 sm:p-6">
        <div className="mx-auto max-w-[1200px]">
          <p className="text-sm text-red-700">{error || "Job not found"}</p>
          <Link
            href="/hr/jobs"
            className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-700 hover:text-brand-800"
          >
            <ArrowLeft className="size-4" />
            Back to Job Offers
          </Link>
        </div>
      </div>
    );
  }

  const employmentLabel =
    EMPLOYMENT_TYPE_LABELS[job.employment_type] || job.employment_type;
  const subtitle =
    [job.department, job.position, job.location].filter(Boolean).join(" · ") ||
    "No location details";

  return (
    <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 pb-8 sm:p-6">
      <div className="mx-auto max-w-[1200px] space-y-5">
        <Link
          href="/hr/jobs"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-[#0f224a]/70 transition hover:text-[#0f224a]"
        >
          <ArrowLeft className="size-4" />
          Back to Job Offers
        </Link>

        {/* Header */}
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight text-brand-900 sm:text-[1.75rem]">
              {job.title}
            </h1>
            <p className="mt-1 text-[13px] text-brand-300">{subtitle}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <StatusPill status={job.status} />
              {job.published_at ? (
                <span className="text-[12px] text-brand-300">
                  Posted on {formatDate(job.published_at)}
                </span>
              ) : (
                <span className="text-[12px] text-brand-300">
                  Created on {formatDate(job.created_at)}
                </span>
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {job.status === "draft" ? (
              <button
                type="button"
                onClick={() => void handlePublish()}
                disabled={acting !== null}
                className="inline-flex h-10 items-center gap-1.5 rounded-xl border border-brand-200 bg-white px-3.5 text-sm font-semibold text-brand-700 transition hover:bg-[#f3f6f5] disabled:opacity-50"
              >
                <CheckCircle2 className="size-4 text-brand-600" />
                {acting === "publish" ? "Publishing..." : "Publish"}
              </button>
            ) : null}
            {job.status === "published" ? (
              <button
                type="button"
                onClick={() => void handleClose()}
                disabled={acting !== null}
                className="inline-flex h-10 items-center gap-1.5 rounded-xl border border-rose-200 bg-white px-3.5 text-sm font-semibold text-rose-700 transition hover:bg-rose-50 disabled:opacity-50"
              >
                <XCircle className="size-4" />
                {acting === "close" ? "Closing..." : "Close offer"}
              </button>
            ) : null}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-brand-200 bg-white text-brand-600 transition hover:bg-[#f3f6f5]"
                  aria-label="More actions"
                >
                  <MoreVertical className="size-4" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => void handleDuplicate()}>
                  <Copy className="size-4" />
                  Duplicate
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => void handleShare()}>
                  <Share2 className="size-4" />
                  Share link
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link href={`/hr/jobs/${job.id}/applications`}>
                    <Users className="size-4" />
                    Applications
                  </Link>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Link
              href={`/hr/jobs/${job.id}/applications`}
              className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700"
            >
              View applications
              <ArrowRight className="size-4" />
            </Link>
          </div>
        </div>

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}
        {notice ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {notice}
          </div>
        ) : null}

        {/* Stats row */}
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
          <StatChip
            label="Employment type"
            value={employmentLabel}
            icon={<Briefcase className="size-3.5" />}
          />
          <StatChip
            label="Location"
            value={job.location || "—"}
            icon={<MapPin className="size-3.5" />}
          />
          <StatChip
            label="Applications"
            value={String(applicationCount)}
            hint={
              newApplicationCount > 0 ? `${newApplicationCount} new` : undefined
            }
            icon={<Users className="size-3.5" />}
          />
          <StatChip
            label="Created"
            value={formatDate(job.created_at)}
            icon={<CalendarDays className="size-3.5" />}
          />
          <StatChip
            label="Published"
            value={formatDate(job.published_at)}
            icon={<CheckCircle2 className="size-3.5" />}
          />
          <StatChip
            label="Closed"
            value={job.closed_at ? formatDate(job.closed_at) : "Not closed"}
            icon={
              job.closed_at ? (
                <XCircle className="size-3.5 text-rose-600" />
              ) : (
                <XCircle className="size-3.5 text-rose-400" />
              )
            }
            tone={job.closed_at ? undefined : "text-rose-600"}
          />
        </div>

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
          {/* Main column */}
          <div className="space-y-5">
            <ContentCard
              title="Job description"
              icon={<FileText className="size-4" />}
            >
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-brand-900/85">
                {job.description}
              </p>
            </ContentCard>

            <ContentCard
              title="Requirements"
              icon={<ListChecks className="size-4" />}
            >
              {requirements.length > 0 ? (
                <ul className="space-y-2.5">
                  {requirements.map((line) => (
                    <li
                      key={line}
                      className="flex items-start gap-2.5 text-sm leading-relaxed text-brand-900/85"
                    >
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-600" />
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-brand-300">No requirements listed.</p>
              )}
            </ContentCard>

            <ContentCard
              title="Application questions"
              icon={<CircleHelp className="size-4" />}
            >
              {job.questions?.length ? (
                <ul className="space-y-3">
                  {job.questions.map((question, index) => (
                    <li
                      key={question.id}
                      className="rounded-xl border border-brand-200/70 bg-[#f7faf9] px-3.5 py-3"
                    >
                      <p className="text-sm font-medium text-brand-900">
                        <span className="mr-2 text-brand-300">{index + 1}.</span>
                        {question.prompt}
                      </p>
                      <p className="mt-1 text-[11px] font-medium uppercase tracking-[0.08em] text-brand-300">
                        {question.question_type.replaceAll("_", " ")}
                        {" · "}
                        {question.required ? "Required" : "Optional"}
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="rounded-xl border border-sky-200 bg-sky-50 px-3.5 py-3 text-sm text-sky-900">
                  No additional questions defined.
                </div>
              )}
            </ContentCard>
          </div>

          {/* Side column */}
          <div className="space-y-5 xl:sticky xl:top-6 xl:self-start">
            <div className={cn(card, "p-5")}>
              <h2 className="text-sm font-semibold text-brand-900">Overview</h2>
              <dl className="mt-4 space-y-3.5">
                <OverviewRow
                  label="Department"
                  value={job.department || "—"}
                  icon={<Building2 className="size-3.5" />}
                />
                <OverviewRow
                  label="Position"
                  value={job.position || "—"}
                  icon={<Briefcase className="size-3.5" />}
                />
                <OverviewRow
                  label="Employment type"
                  value={employmentLabel}
                  icon={<ClipboardList className="size-3.5" />}
                />
                {job.employment_type === "internship" ? (
                  <OverviewRow
                    label="Internship duration"
                    value={
                      job.internship_duration_months
                        ? `${job.internship_duration_months} month${
                            job.internship_duration_months === 1 ? "" : "s"
                          }`
                        : "—"
                    }
                    icon={<CalendarDays className="size-3.5" />}
                  />
                ) : null}
                <OverviewRow
                  label="Location"
                  value={job.location || "—"}
                  icon={<MapPin className="size-3.5" />}
                />
                <div className="flex items-start justify-between gap-3">
                  <dt className="text-[12px] text-brand-300">Status</dt>
                  <dd>
                    <StatusPill status={job.status} />
                  </dd>
                </div>
                <OverviewRow
                  label="Created at"
                  value={formatDate(job.created_at)}
                />
                <OverviewRow
                  label="Published at"
                  value={formatDate(job.published_at)}
                />
                <OverviewRow
                  label="Closed at"
                  value={formatDate(job.closed_at)}
                />
              </dl>
            </div>

            <div className={cn(card, "overflow-hidden")}>
              <div className="border-b border-brand-200/70 px-5 py-4">
                <h2 className="text-sm font-semibold text-brand-900">
                  Quick actions
                </h2>
              </div>
              <div className="divide-y divide-brand-200/60">
                <QuickAction
                  href={`/hr/jobs/${job.id}/applications`}
                  title="View applications"
                  description="See and manage all candidate applications"
                  icon={<Users className="size-4" />}
                />
                <QuickAction
                  onClick={() => void handleDuplicate()}
                  title="Duplicate job offer"
                  description="Create a new offer from this one"
                  icon={<Copy className="size-4" />}
                  disabled={acting === "duplicate"}
                />
                <QuickAction
                  onClick={() => void handleShare()}
                  title="Share job offer"
                  description="Copy link to share the job posting"
                  icon={<Link2 className="size-4" />}
                />
              </div>
            </div>
          </div>
        </div>
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

function StatChip({
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
  tone?: string;
}) {
  return (
    <div className={cn(card, "px-3 py-2.5")}>
      <div className="flex items-center gap-1.5 text-brand-300">
        {icon}
        <p className="text-[10px] font-semibold uppercase tracking-[0.1em]">
          {label}
        </p>
      </div>
      <p
        className={cn(
          "mt-1 truncate text-sm font-semibold text-brand-900",
          tone
        )}
      >
        {value}
      </p>
      {hint ? (
        <p className="mt-0.5 truncate text-[11px] text-brand-300">{hint}</p>
      ) : null}
    </div>
  );
}

function ContentCard({
  title,
  icon,
  children,
}: {
  title: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className={cn(card, "p-5 sm:p-6")}>
      <div className="mb-4 flex items-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#f3f6f5] text-brand-700">
          {icon}
        </span>
        <h2 className="text-sm font-semibold text-brand-900">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function OverviewRow({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-[12px] text-brand-300">{label}</dt>
      <dd className="flex max-w-[60%] items-center justify-end gap-1.5 text-right text-sm font-medium text-brand-900">
        {icon ? <span className="text-brand-300">{icon}</span> : null}
        <span className="truncate">{value}</span>
      </dd>
    </div>
  );
}

function QuickAction({
  title,
  description,
  icon,
  href,
  onClick,
  disabled,
}: {
  title: string;
  description: string;
  icon: ReactNode;
  href?: string;
  onClick?: () => void;
  disabled?: boolean;
}) {
  const className = cn(
    "flex w-full items-start gap-3 px-5 py-4 text-left transition hover:bg-[#f7faf9]",
    disabled && "pointer-events-none opacity-50"
  );

  const content = (
    <>
      <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#f3f6f5] text-brand-700">
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold text-brand-900">{title}</span>
        <span className="mt-0.5 block text-[12px] text-brand-300">
          {description}
        </span>
      </span>
      <ArrowRight className="mt-1 size-4 shrink-0 text-brand-300" />
    </>
  );

  if (href) {
    return (
      <Link href={href} className={className}>
        {content}
      </Link>
    );
  }

  return (
    <button type="button" onClick={onClick} disabled={disabled} className={className}>
      {content}
    </button>
  );
}

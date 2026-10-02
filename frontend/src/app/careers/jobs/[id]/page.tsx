"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useEffect, useState, type ReactNode } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Briefcase,
  Building2,
  CalendarDays,
  CheckCircle2,
  Clock3,
  FileText,
  ListChecks,
  MapPin,
} from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { EMPLOYMENT_TYPE_LABELS } from "@/types/employees";
import type { ApplicationDetail } from "@/types/applications";
import type { EmploymentType, Job } from "@/types/jobs";
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

function employmentTone(type: EmploymentType): string {
  if (type === "internship") return "bg-amber-50 text-amber-800";
  if (type === "contract") return "bg-sky-50 text-sky-800";
  if (type === "part_time") return "bg-violet-50 text-violet-800";
  return "bg-emerald-50 text-emerald-800";
}

function requirementLines(requirements: string | null): string[] {
  if (!requirements?.trim()) return [];
  return requirements
    .split(/\r?\n|•|;/)
    .map((line) => line.replace(/^[-*]\s*/, "").trim())
    .filter(Boolean);
}

export default function CareerJobDetailPage() {
  const params = useParams<{ id: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [existingApplication, setExistingApplication] =
    useState<ApplicationDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const jobId = Number(params.id);

  useEffect(() => {
    const load = async () => {
      setError("");
      setLoading(true);
      try {
        setJob(await api.getCareerJob(jobId));
        try {
          setExistingApplication(await api.getMyJobApplication(jobId));
        } catch {
          setExistingApplication(null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load job");
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
    [job]
  );

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center bg-[#f3f6f5] p-6">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="min-h-full bg-[#f3f6f5] p-5 sm:p-6">
        <div className="mx-auto max-w-[1100px]">
          <p className="text-sm text-red-700">{error || "Job not found"}</p>
          <Link
            href="/careers/jobs"
            className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-brand-700"
          >
            <ArrowLeft className="size-4" />
            Back to openings
          </Link>
        </div>
      </div>
    );
  }

  const employmentLabel =
    EMPLOYMENT_TYPE_LABELS[job.employment_type] || job.employment_type;

  return (
    <div className="min-h-full bg-[#f3f6f5] p-5 pb-8 sm:p-6">
      <div className="mx-auto max-w-[1100px] space-y-5">
        <Link
          href="/careers/jobs"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-[#0f224a]/70 transition hover:text-[#0f224a]"
        >
          <ArrowLeft className="size-4" />
          Back to openings
        </Link>

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {/* Hero */}
        <section className={cn(card, "overflow-hidden")}>
          <div className="relative bg-gradient-to-r from-[#0b2a3a] via-[#0f3d48] to-[#117a5f] px-6 py-7 sm:px-8 sm:py-8">
            <div
              className="pointer-events-none absolute -right-6 top-0 h-36 w-56 opacity-40"
              aria-hidden
            >
              <svg viewBox="0 0 240 140" fill="none" className="h-full w-full">
                <path
                  d="M0 80 C50 30, 100 120, 160 60 C190 30, 220 70, 240 45"
                  stroke="#ffffff"
                  strokeWidth="2"
                  strokeLinecap="round"
                  opacity="0.35"
                />
              </svg>
            </div>
            <p className="relative text-[11px] font-semibold uppercase tracking-[0.18em] text-white/55">
              Open role
            </p>
            <h1 className="relative mt-2 max-w-3xl text-2xl font-semibold tracking-tight text-white sm:text-[1.85rem]">
              {job.title}
            </h1>
            <div className="relative mt-3 flex flex-wrap items-center gap-2">
              <span
                className={cn(
                  "inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold",
                  employmentTone(job.employment_type)
                )}
              >
                {employmentLabel}
              </span>
              {job.department ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-white/10 px-2.5 py-1 text-[11px] font-medium text-white/90">
                  <Building2 className="size-3.5" />
                  {job.department}
                </span>
              ) : null}
              {job.location ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-white/10 px-2.5 py-1 text-[11px] font-medium text-white/90">
                  <MapPin className="size-3.5" />
                  {job.location}
                </span>
              ) : null}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 border-t border-brand-200/60 p-4 sm:grid-cols-3 sm:p-5">
            <MetaStat
              icon={<Briefcase className="size-4" />}
              label="Employment"
              value={employmentLabel}
              tone="bg-emerald-50 text-emerald-700"
            />
            <MetaStat
              icon={<Building2 className="size-4" />}
              label="Department"
              value={job.department || job.position || "—"}
              tone="bg-sky-50 text-sky-700"
            />
            <MetaStat
              icon={<CalendarDays className="size-4" />}
              label="Published"
              value={formatDate(job.published_at)}
              tone="bg-teal-50 text-teal-700"
            />
          </div>
        </section>

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-5">
            <section className={cn(card, "p-5 sm:p-6")}>
              <div className="mb-3 flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#f3f6f5] text-brand-700">
                  <FileText className="size-4" />
                </span>
                <h2 className="text-sm font-semibold text-brand-900">
                  About the role
                </h2>
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-brand-900/85">
                {job.description}
              </p>
            </section>

            <section className={cn(card, "p-5 sm:p-6")}>
              <div className="mb-3 flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#f3f6f5] text-brand-700">
                  <ListChecks className="size-4" />
                </span>
                <h2 className="text-sm font-semibold text-brand-900">
                  Requirements
                </h2>
              </div>
              {requirements.length === 0 ? (
                <p className="text-sm text-brand-300">
                  No specific requirements listed.
                </p>
              ) : (
                <ul className="space-y-2.5">
                  {requirements.map((line) => (
                    <li key={line} className="flex items-start gap-2.5 text-sm text-brand-900/85">
                      <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-brand-600" />
                      <span>{line}</span>
                    </li>
                  ))}
                </ul>
              )}
              {job.employment_type === "internship" &&
              job.internship_duration_months ? (
                <p className="mt-4 rounded-xl bg-[#f7faf9] px-3 py-2 text-[13px] text-brand-700">
                  Internship duration:{" "}
                  <span className="font-semibold">
                    {job.internship_duration_months} month
                    {job.internship_duration_months === 1 ? "" : "s"}
                  </span>
                </p>
              ) : null}
            </section>

            {job.questions.length > 0 ? (
              <section className={cn(card, "p-5 sm:p-6")}>
                <div className="mb-3 flex items-center gap-2">
                  <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#f3f6f5] text-brand-700">
                    <ListChecks className="size-4" />
                  </span>
                  <div>
                    <h2 className="text-sm font-semibold text-brand-900">
                      Application questions
                    </h2>
                    <p className="text-[12px] text-brand-300">
                      You&apos;ll answer these when you apply
                    </p>
                  </div>
                </div>
                <ul className="space-y-2">
                  {job.questions
                    .slice()
                    .sort((a, b) => a.display_order - b.display_order)
                    .map((question, index) => (
                      <li
                        key={question.id}
                        className="rounded-xl border border-brand-200/60 bg-[#f7faf9] px-4 py-3"
                      >
                        <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
                          Question {index + 1}
                          {question.required ? " · Required" : " · Optional"}
                        </p>
                        <p className="mt-1 text-sm font-medium text-brand-900">
                          {question.prompt}
                        </p>
                      </li>
                    ))}
                </ul>
              </section>
            ) : null}
          </div>

          <aside className="space-y-4 xl:sticky xl:top-5 xl:self-start">
            <section className={cn(card, "p-5")}>
              <h2 className="text-sm font-semibold text-brand-900">
                Ready to apply?
              </h2>
              <p className="mt-1 text-[13px] leading-relaxed text-brand-300">
                Submit your CV and answers in a few minutes. You can track your
                application status from your careers workspace.
              </p>

              {existingApplication ? (
                <div className="mt-4 space-y-3 rounded-xl border border-brand-200/70 bg-[#f7faf9] p-4">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="size-4 text-brand-600" />
                    <p className="text-sm font-semibold text-brand-900">
                      Already applied
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-[13px] text-brand-300">
                    <span>Status</span>
                    <StatusBadge status={existingApplication.status} />
                  </div>
                  <p className="text-[12px] text-brand-300">
                    Submitted {formatDate(existingApplication.submitted_at)}
                  </p>
                </div>
              ) : (
                <Link
                  href={`/careers/jobs/${job.id}/apply`}
                  className="mt-4 inline-flex h-11 w-full items-center justify-center gap-1.5 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700"
                >
                  Apply now
                  <ArrowRight className="size-4" />
                </Link>
              )}
            </section>

            <section className={cn(card, "space-y-3 p-5")}>
              <h2 className="text-sm font-semibold text-brand-900">
                Role snapshot
              </h2>
              <SnapshotRow
                icon={<MapPin className="size-3.5" />}
                label="Location"
                value={job.location || "Not specified"}
              />
              <SnapshotRow
                icon={<Building2 className="size-3.5" />}
                label="Department"
                value={job.department || "Not specified"}
              />
              <SnapshotRow
                icon={<Briefcase className="size-3.5" />}
                label="Type"
                value={employmentLabel}
              />
              <SnapshotRow
                icon={<Clock3 className="size-3.5" />}
                label="Posted"
                value={formatDate(job.published_at)}
              />
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}

function MetaStat({
  icon,
  label,
  value,
  tone,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  tone: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl bg-[#f7faf9] px-3 py-3">
      <span
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
          tone
        )}
      >
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
          {label}
        </p>
        <p className="truncate text-sm font-semibold text-brand-900">{value}</p>
      </div>
    </div>
  );
}

function SnapshotRow({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start gap-2.5">
      <span className="mt-0.5 text-brand-300">{icon}</span>
      <div className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
          {label}
        </p>
        <p className="text-sm font-medium text-brand-900">{value}</p>
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Award,
  Briefcase,
  CalendarDays,
  Check,
  ChevronDown,
  FileText,
  GraduationCap,
  Lightbulb,
  MessageSquareText,
  MoreVertical,
  Sparkles,
  Target,
  Users,
  Video,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MeetingJoinBlock } from "@/components/MeetingJoinBlock";
import { api } from "@/lib/api";
import { formatSlotRange, hasActiveInterviewInvitation } from "@/lib/interviews";
import type {
  ApplicationDetail,
  ApplicationDocument,
  ApplicationStatus,
  EducationEntry,
  ExperienceEntry,
  FitAssessment,
} from "@/types/applications";
import type { InterviewOutcome, InterviewSummary } from "@/types/interviews";
import { cn } from "@/lib/utils";

const card =
  "rounded-2xl border border-brand-200/70 bg-white shadow-[0_8px_24px_-18px_rgba(15,34,74,0.35)]";

type TabId =
  | "overview"
  | "documents"
  | "experience"
  | "education"
  | "questions"
  | "files"
  | "interviews";

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

const MOVE_TARGETS: Partial<Record<ApplicationStatus, ApplicationStatus[]>> = {
  submitted: ["screening", "rejected"],
  screening: ["shortlisted", "rejected"],
  shortlisted: ["rejected"],
};

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatYears(startYear?: number | null, endYear?: number | null): string | null {
  if (startYear && endYear) return `${startYear}–${endYear}`;
  if (startYear && !endYear) return `${startYear}–present`;
  if (!startYear && endYear) return String(endYear);
  return null;
}

function sortExperience<T extends ExperienceEntry>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    const aEnd = a.end_year ?? Number.MAX_SAFE_INTEGER;
    const bEnd = b.end_year ?? Number.MAX_SAFE_INTEGER;
    if (aEnd !== bEnd) return bEnd - aEnd;
    return (b.start_year ?? 0) - (a.start_year ?? 0);
  });
}

function isPdf(document: ApplicationDocument): boolean {
  return (
    document.content_type === "application/pdf" ||
    document.original_filename.toLowerCase().endsWith(".pdf")
  );
}

function initials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

function fitRingColor(score: number): string {
  if (score < 30) return "#dc2626";
  if (score < 60) return "#f97316";
  return "#16a34a";
}

function fitLevelLabel(level: string, score: number): string {
  if (level === "GOOD" || score >= 80) return "Excellent match";
  if (level === "MEDIUM" || score >= 60) return "Good match";
  if (level === "BAD" || score < 30) return "Weak match";
  return "Moderate match";
}

function clampScore(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function deriveBars(fit: FitAssessment) {
  const matched = fit.matching_skills.length;
  const missing = fit.missing_skills.length;
  const total = matched + missing;
  const skillRatio = total === 0 ? fit.fit_score : (matched / total) * 100;

  const experienceBoost =
    fit.experience_match && /strong|excellent|good|relevant/i.test(fit.experience_match)
      ? 8
      : fit.experience_match && /limited|weak|missing/i.test(fit.experience_match)
        ? -10
        : 0;
  const educationBoost =
    fit.education_match && /strong|excellent|good|relevant/i.test(fit.education_match)
      ? 6
      : fit.education_match && /limited|weak|missing/i.test(fit.education_match)
        ? -8
        : 0;

  return {
    technical: clampScore(skillRatio),
    experience: clampScore(fit.fit_score + experienceBoost),
    education: clampScore(fit.fit_score + educationBoost - 4),
  };
}

export default function ApplicationDetailPage() {
  const params = useParams<{ id: string }>();
  const applicationId = Number(params.id);
  const [application, setApplication] = useState<ApplicationDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<number | null>(null);
  const [preview, setPreview] = useState<{ document: ApplicationDocument; url: string } | null>(
    null
  );
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [interviews, setInterviews] = useState<InterviewSummary[]>([]);
  const [interviewsError, setInterviewsError] = useState("");
  const [outcomeActingId, setOutcomeActingId] = useState<number | null>(null);
  const [meetingRetryId, setMeetingRetryId] = useState<number | null>(null);
  const [hireConfirmId, setHireConfirmId] = useState<number | null>(null);
  const [successMessage, setSuccessMessage] = useState("");
  const [tab, setTab] = useState<TabId>("overview");
  const [openAccordion, setOpenAccordion] = useState<string | null>(null);

  const loadInterviews = async () => {
    try {
      setInterviewsError("");
      setInterviews(await api.listApplicationInterviews(applicationId));
    } catch (err) {
      setInterviews([]);
      setInterviewsError(
        err instanceof Error ? err.message : "Failed to load interviews"
      );
    }
  };

  useEffect(() => {
    const load = async () => {
      setError("");
      setLoading(true);
      try {
        const data = await api.getApplication(applicationId);
        setApplication(data);
        await loadInterviews();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load application");
      } finally {
        setLoading(false);
      }
    };
    if (!Number.isNaN(applicationId)) {
      void load();
    }
  }, [applicationId]);

  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState === "visible") {
        void loadInterviews();
      }
    };
    document.addEventListener("visibilitychange", refresh);
    return () => document.removeEventListener("visibilitychange", refresh);
  }, [applicationId]);

  const viewDocument = async (document: ApplicationDocument) => {
    setActingId(document.id);
    setError("");
    try {
      if (!isPdf(document)) {
        setPreview({ document, url: "" });
        setTab("documents");
        return;
      }
      const result = await api.getApplicationDocumentUrl(
        applicationId,
        document.id,
        false
      );
      setPreview({ document, url: result.url });
      setTab("documents");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open document");
    } finally {
      setActingId(null);
    }
  };

  const downloadDocument = async (document: ApplicationDocument) => {
    setActingId(document.id);
    setError("");
    try {
      const result = await api.getApplicationDocumentUrl(
        applicationId,
        document.id,
        true
      );
      window.open(result.url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download document");
    } finally {
      setActingId(null);
    }
  };

  const changeStatus = async (status: ApplicationStatus) => {
    if (!application || status === application.status) return;
    setUpdatingStatus(true);
    setError("");
    setSuccessMessage("");
    try {
      const updated = await api.updateApplicationStatus(applicationId, status);
      setApplication(updated);
      setSuccessMessage(`Status updated to ${STATUS_PILL[status].label}.`);
      await loadInterviews();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update status");
    } finally {
      setUpdatingStatus(false);
    }
  };

  const submitOutcome = async (interviewId: number, outcome: InterviewOutcome) => {
    setOutcomeActingId(interviewId);
    setError("");
    setSuccessMessage("");
    try {
      const updatedInterview = await api.recordInterviewOutcome(interviewId, {
        outcome,
      });
      setHireConfirmId(null);
      setApplication(await api.getApplication(applicationId));
      await loadInterviews();
      if (outcome === "hired") {
        setSuccessMessage(
          updatedInterview.hired_employee_id
            ? "Candidate hired. Employee record created."
            : "Candidate hired."
        );
      } else if (outcome === "rejected") {
        setSuccessMessage("Candidate rejected. Application status updated.");
      } else {
        setSuccessMessage(
          "Marked for another interview. You can send a new invitation."
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record outcome");
    } finally {
      setOutcomeActingId(null);
    }
  };

  const retryMeetingLink = async (interviewId: number) => {
    setMeetingRetryId(interviewId);
    setError("");
    setSuccessMessage("");
    try {
      await api.ensureInterviewMeeting(interviewId);
      await loadInterviews();
      setSuccessMessage("Meeting link refreshed.");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to provision meeting link"
      );
    } finally {
      setMeetingRetryId(null);
    }
  };

  const experience = useMemo(
    () => (application ? sortExperience(application.experience) : []),
    [application]
  );

  const cvDocument = application?.documents.find((doc) => doc.kind === "cv");
  const coverDocument = application?.documents.find(
    (doc) => doc.kind === "cover_letter"
  );

  if (loading) {
    return (
      <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 sm:p-6">
        <div className="flex justify-center py-20">
          <div className="h-7 w-7 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
        </div>
      </div>
    );
  }

  if (!application) {
    return (
      <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 sm:p-6">
        <p className="text-sm text-red-700">{error || "Application not found"}</p>
      </div>
    );
  }

  const moveTargets = MOVE_TARGETS[application.status] ?? [];
  const hasPendingInvitation = interviews.some(
    (interview) => interview.status === "proposed"
  );
  const hasActiveInvitation = hasActiveInterviewInvitation(interviews);
  const hasPendingOutcome = interviews.some(
    (interview) => interview.status === "completed" && !interview.outcome
  );
  const hiredEmployeeId =
    interviews.find((interview) => interview.hired_employee_id)
      ?.hired_employee_id ?? null;
  const canInvite =
    application.status === "shortlisted" && !hasActiveInvitation && !hasPendingOutcome;
  const fit = application.fit_assessment;
  const bars = fit ? deriveBars(fit) : null;
  const strengths = (fit?.matching_skills ?? []).slice(0, 3);

  const tabs: Array<{ id: TabId; label: string }> = [
    { id: "overview", label: "Overview" },
    { id: "documents", label: "CV & Cover Letter" },
    { id: "experience", label: "Experience" },
    { id: "education", label: "Education" },
    { id: "questions", label: "Questions & Answers" },
    { id: "files", label: "Documents" },
    { id: "interviews", label: "Interviews" },
  ];

  return (
    <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 pb-8 sm:p-6">
      <div className="mx-auto max-w-[1200px] space-y-5">
        <Link
          href={`/hr/jobs/${application.job.id}/applications`}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-[#0f224a]/70 transition hover:text-[#0f224a]"
        >
          <ArrowLeft className="size-4" />
          Back to applications
        </Link>

        {/* Header */}
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight text-brand-900">
                {application.candidate.full_name}
              </h1>
              <StatusPill status={application.status} />
            </div>
            <p className="mt-1 text-[13px] text-brand-300">
              Applied for {application.job.title}
              {application.job.department ? ` · ${application.job.department}` : ""}
              {" · "}
              Applied on {formatDate(application.submitted_at)}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  disabled={updatingStatus || moveTargets.length === 0}
                  className="inline-flex h-10 items-center gap-1.5 rounded-xl border border-brand-200 bg-white px-3.5 text-sm font-semibold text-brand-700 transition hover:bg-[#f3f6f5] disabled:opacity-50"
                >
                  Move to
                  <ChevronDown className="size-4" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {moveTargets.map((status) => (
                  <DropdownMenuItem
                    key={status}
                    onSelect={() => {
                      void changeStatus(status);
                    }}
                  >
                    {STATUS_PILL[status].label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>

            {canInvite ? (
              <Link
                href={`/hr/applications/${applicationId}/invite`}
                className="inline-flex h-10 items-center gap-1.5 rounded-xl border border-brand-200 bg-white px-3.5 text-sm font-semibold text-brand-700 transition hover:bg-[#f3f6f5]"
              >
                <CalendarDays className="size-4" />
                Schedule interview
              </Link>
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
                <DropdownMenuItem asChild>
                  <Link href={`/hr/jobs/${application.job.id}`}>
                    View job offer
                  </Link>
                </DropdownMenuItem>
                {hiredEmployeeId ? (
                  <DropdownMenuItem asChild>
                    <Link href={`/hr/employees/${hiredEmployeeId}`}>
                      View employee
                    </Link>
                  </DropdownMenuItem>
                ) : null}
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onSelect={() => {
                    void changeStatus("rejected");
                  }}
                  disabled={application.status === "rejected"}
                >
                  Reject candidate
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            {cvDocument ? (
              <button
                type="button"
                disabled={actingId === cvDocument.id}
                onClick={() => void viewDocument(cvDocument)}
                className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-brand-600 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 disabled:opacity-50"
              >
                <FileText className="size-4" />
                {actingId === cvDocument.id ? "Opening..." : "View CV"}
              </button>
            ) : null}
          </div>
        </div>

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}
        {successMessage ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {successMessage}
          </div>
        ) : null}

        {/* Candidate + Fit cards */}
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <section className={cn(card, "p-5")}>
            <div className="flex items-start gap-4">
              <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-[#0f224a] text-lg font-semibold text-white shadow-sm">
                {initials(application.candidate.full_name)}
              </span>
              <div className="min-w-0 space-y-2">
                <div>
                  <p className="text-base font-semibold text-brand-900">
                    {application.candidate.full_name}
                  </p>
                  <p className="text-[13px] text-brand-300">Candidate</p>
                </div>
                <InfoLine label="Email" value={application.candidate.email} />
                <InfoLine
                  label="Phone"
                  value={application.candidate.phone || "—"}
                />
              </div>
            </div>
          </section>

          <section className={cn(card, "p-5")}>
            {fit ? (
              <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
                <FitScoreRing score={fit.fit_score} />
                <div className="min-w-0 flex-1 space-y-3">
                  <div>
                    <p className="text-sm font-semibold text-brand-900">
                      {fitLevelLabel(fit.fit_level, fit.fit_score)}
                    </p>
                    <p className="mt-1 text-[13px] leading-relaxed text-brand-300">
                      {fit.explanation
                        ? fit.explanation.slice(0, 160) +
                          (fit.explanation.length > 160 ? "…" : "")
                        : "AI fit assessment based on CV, experience and job requirements."}
                    </p>
                  </div>
                  {bars ? (
                    <div className="space-y-2.5">
                      <SkillBar label="Technical skills" value={bars.technical} />
                      <SkillBar
                        label="Relevant experience"
                        value={bars.experience}
                      />
                      <SkillBar
                        label="Education & background"
                        value={bars.education}
                      />
                    </div>
                  ) : null}
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-3 py-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#f3f6f5] text-brand-600">
                  <Sparkles className="size-5" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-brand-900">
                    Fit analysis pending
                  </p>
                  <p className="text-[13px] text-brand-300">
                    Refresh shortly after a new application.
                  </p>
                </div>
              </div>
            )}
          </section>
        </div>

        {/* Application details */}
        <section className={cn(card, "overflow-hidden")}>
          <div className="grid grid-cols-1 gap-4 p-5 sm:grid-cols-2 xl:grid-cols-4">
            <Detail label="Job title" value={application.job.title} />
            <Detail
              label="Department"
              value={application.job.department || "—"}
            />
            <Detail
              label="Application date"
              value={formatDate(application.submitted_at)}
            />
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
                Status
              </p>
              <div className="mt-1.5">
                <StatusPill status={application.status} />
              </div>
            </div>
          </div>

          {application.status === "hired" && hiredEmployeeId ? (
            <div className="border-t border-brand-200/70 bg-emerald-50 px-5 py-3 text-sm text-emerald-900">
              Employee created.{" "}
              <Link
                href={`/hr/employees/${hiredEmployeeId}`}
                className="font-semibold underline underline-offset-2"
              >
                View employee record
              </Link>
            </div>
          ) : null}

          {hasPendingInvitation ? (
            <Banner tone="amber">
              {interviews.some(
                (interview) =>
                  interview.status === "proposed" && (interview.slot_count ?? 0) === 0
              )
                ? "Waiting for the primary interviewer to propose available slots."
                : "Waiting for the candidate to choose a slot."}
            </Banner>
          ) : null}

          {!hasPendingInvitation && hasActiveInvitation && !hasPendingOutcome ? (
            <Banner tone="green" icon={<CalendarDays className="size-4" />}>
              Interview is scheduled. A new invitation cannot be created until this
              interview is completed or cancelled.
            </Banner>
          ) : null}

          {hasPendingOutcome ? (
            <Banner tone="amber">
              Interview completed. Record an outcome before inviting again.
            </Banner>
          ) : null}

          {interviewsError ? (
            <Banner tone="red">{interviewsError}</Banner>
          ) : null}
        </section>

        {/* Tabs */}
        <div className={cn(card, "overflow-hidden")}>
          <div className="flex gap-1 overflow-x-auto border-b border-brand-200/70 px-2">
            {tabs.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setTab(item.id)}
                className={cn(
                  "shrink-0 border-b-2 px-3.5 py-3 text-sm font-semibold transition",
                  tab === item.id
                    ? "border-brand-600 text-brand-700"
                    : "border-transparent text-brand-300 hover:text-brand-700"
                )}
              >
                {item.label}
              </button>
            ))}
          </div>

          <div className="p-5 sm:p-6">
            {tab === "overview" ? (
              <OverviewTab
                fit={fit}
                experienceCount={experience.length}
                educationCount={application.education.length}
                answersCount={application.answers.length}
                documentsCount={application.documents.length}
                interviewsCount={interviews.length}
                strengths={strengths}
                openAccordion={openAccordion}
                onToggleAccordion={(id) =>
                  setOpenAccordion((current) => (current === id ? null : id))
                }
                onGoTab={setTab}
                experience={experience}
                education={application.education}
                answers={application.answers}
                documents={application.documents}
                interviews={interviews}
              />
            ) : null}

            {tab === "documents" ? (
              <DocumentsPanel
                cv={cvDocument}
                cover={coverDocument}
                preview={preview}
                actingId={actingId}
                onView={viewDocument}
                onDownload={downloadDocument}
                onClosePreview={() => setPreview(null)}
              />
            ) : null}

            {tab === "experience" ? (
              <ExperiencePanel items={experience} />
            ) : null}

            {tab === "education" ? (
              <EducationPanel items={application.education} />
            ) : null}

            {tab === "questions" ? (
              <QuestionsPanel answers={application.answers} />
            ) : null}

            {tab === "files" ? (
              <FilesPanel
                documents={application.documents}
                actingId={actingId}
                onView={viewDocument}
                onDownload={downloadDocument}
                preview={preview}
                onClosePreview={() => setPreview(null)}
              />
            ) : null}

            {tab === "interviews" ? (
              <InterviewsPanel
                interviews={interviews}
                outcomeActingId={outcomeActingId}
                meetingRetryId={meetingRetryId}
                hireConfirmId={hireConfirmId}
                onRetryMeeting={retryMeetingLink}
                onOutcome={submitOutcome}
                onAskHire={setHireConfirmId}
              />
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function OverviewTab({
  fit,
  experienceCount,
  educationCount,
  answersCount,
  documentsCount,
  interviewsCount,
  strengths,
  openAccordion,
  onToggleAccordion,
  onGoTab,
  experience,
  education,
  answers,
  documents,
  interviews,
}: {
  fit?: FitAssessment | null;
  experienceCount: number;
  educationCount: number;
  answersCount: number;
  documentsCount: number;
  interviewsCount: number;
  strengths: string[];
  openAccordion: string | null;
  onToggleAccordion: (id: string) => void;
  onGoTab: (tab: TabId) => void;
  experience: Array<ExperienceEntry & { id: number }>;
  education: Array<EducationEntry & { id: number }>;
  answers: ApplicationDetail["answers"];
  documents: ApplicationDocument[];
  interviews: InterviewSummary[];
}) {
  return (
    <div className="space-y-6">
      <section>
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Sparkles className="size-4 text-brand-600" />
            <h2 className="text-sm font-semibold text-brand-900">Matching skills</h2>
          </div>
          {fit ? (
            <button
              type="button"
              onClick={() => onGoTab("overview")}
              className="text-xs font-semibold text-brand-600 hover:text-brand-700"
            >
              View detailed analysis
            </button>
          ) : null}
        </div>
        {fit && fit.matching_skills.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {fit.matching_skills.map((skill) => (
              <span
                key={skill}
                className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-[12px] font-semibold text-emerald-800"
              >
                <Check className="size-3.5" />
                {skill}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-sm text-brand-300">No matching skills identified yet.</p>
        )}
        {fit && fit.missing_skills.length > 0 ? (
          <div className="mt-3">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
              Gaps / not identified
            </p>
            <div className="flex flex-wrap gap-2">
              {fit.missing_skills.map((skill) => (
                <span
                  key={skill}
                  className="inline-flex rounded-full bg-rose-50 px-3 py-1 text-[12px] font-medium text-rose-700"
                >
                  {skill}
                </span>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      <section>
        <div className="mb-3 flex items-center gap-2">
          <Target className="size-4 text-brand-600" />
          <h2 className="text-sm font-semibold text-brand-900">Candidate summary</h2>
        </div>
        <div className="space-y-3 text-sm leading-relaxed text-brand-900/85">
          {fit?.explanation ? (
            fit.explanation
              .split(/\n+/)
              .filter(Boolean)
              .slice(0, 3)
              .map((paragraph) => <p key={paragraph}>{paragraph}</p>)
          ) : (
            <p className="text-brand-300">
              AI summary will appear here once the fit assessment is ready.
            </p>
          )}
          {fit?.experience_match ? (
            <p>
              <span className="font-semibold text-brand-900">Experience: </span>
              {fit.experience_match}
            </p>
          ) : null}
          {fit?.education_match ? (
            <p>
              <span className="font-semibold text-brand-900">Education: </span>
              {fit.education_match}
            </p>
          ) : null}
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-center gap-2">
          <Award className="size-4 text-brand-600" />
          <h2 className="text-sm font-semibold text-brand-900">Key strengths</h2>
        </div>
        {strengths.length > 0 ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {strengths.map((item, index) => {
              const icons = [
                <Award key="a" className="size-4" />,
                <Lightbulb key="l" className="size-4" />,
                <Users key="u" className="size-4" />,
              ];
              return (
                <div
                  key={item}
                  className="rounded-xl border border-brand-200/70 bg-[#f7faf9] p-4"
                >
                  <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-lg bg-white text-brand-700 shadow-sm">
                    {icons[index] ?? <Sparkles className="size-4" />}
                  </div>
                  <p className="text-sm font-semibold text-brand-900">{item}</p>
                  <p className="mt-1 text-[12px] text-brand-300">
                    Highlighted as a matching skill for this role.
                  </p>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-brand-300">No key strengths extracted yet.</p>
        )}
      </section>

      <section className="overflow-hidden rounded-xl border border-brand-200/70">
        <AccordionRow
          icon={<Briefcase className="size-4" />}
          title="Work experience"
          count={`${experienceCount} position${experienceCount === 1 ? "" : "s"}`}
          open={openAccordion === "experience"}
          onToggle={() => onToggleAccordion("experience")}
        >
          <ExperiencePanel items={experience} compact />
        </AccordionRow>
        <AccordionRow
          icon={<GraduationCap className="size-4" />}
          title="Education"
          count={`${educationCount} degree${educationCount === 1 ? "" : "s"}`}
          open={openAccordion === "education"}
          onToggle={() => onToggleAccordion("education")}
        >
          <EducationPanel items={education} compact />
        </AccordionRow>
        <AccordionRow
          icon={<MessageSquareText className="size-4" />}
          title="Application questions"
          count={`${answersCount} answer${answersCount === 1 ? "" : "s"}`}
          open={openAccordion === "questions"}
          onToggle={() => onToggleAccordion("questions")}
        >
          <QuestionsPanel answers={answers} compact />
        </AccordionRow>
        <AccordionRow
          icon={<FileText className="size-4" />}
          title="Documents"
          count={`${documentsCount} file${documentsCount === 1 ? "" : "s"}`}
          open={openAccordion === "documents"}
          onToggle={() => onToggleAccordion("documents")}
        >
          <ul className="space-y-2 text-sm text-brand-700">
            {documents.map((doc) => (
              <li key={doc.id}>
                {doc.kind === "cv" ? "CV" : "Cover letter"}: {doc.original_filename}
              </li>
            ))}
            {documents.length === 0 ? (
              <li className="text-brand-300">No documents uploaded.</li>
            ) : null}
          </ul>
        </AccordionRow>
        <AccordionRow
          icon={<Video className="size-4" />}
          title="Interview history"
          count={`${interviewsCount} interview${interviewsCount === 1 ? "" : "s"}`}
          open={openAccordion === "interviews"}
          onToggle={() => onToggleAccordion("interviews")}
          last
        >
          {interviews.length === 0 ? (
            <p className="text-sm text-brand-300">No interviews yet.</p>
          ) : (
            <ul className="space-y-2 text-sm text-brand-700">
              {interviews.map((interview) => (
                <li key={interview.id}>
                  {interview.status_label}
                  {interview.selected_slot
                    ? ` · ${formatSlotRange(
                        interview.selected_slot.starts_at,
                        interview.selected_slot.ends_at
                      )}`
                    : ""}
                </li>
              ))}
            </ul>
          )}
        </AccordionRow>
      </section>
    </div>
  );
}

function ExperiencePanel({
  items,
  compact = false,
}: {
  items: Array<ExperienceEntry & { id: number }>;
  compact?: boolean;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-brand-300">No experience provided.</p>;
  }
  return (
    <div className={cn("space-y-4", compact && "space-y-3")}>
      {items.map((item, index) => {
        const years = formatYears(item.start_year, item.end_year);
        return (
          <div
            key={item.id}
            className={cn(
              !compact && "rounded-xl border border-brand-200/70 bg-[#f7faf9] p-4"
            )}
          >
            <p className="text-sm font-semibold text-brand-900">
              {item.title} · {item.company}
              {index === 0 ? (
                <span className="ml-2 text-[11px] font-medium text-brand-300">
                  Most recent
                </span>
              ) : null}
            </p>
            {years ? (
              <p className="mt-0.5 text-[13px] text-brand-300">{years}</p>
            ) : null}
            {item.description ? (
              <p className="mt-2 whitespace-pre-wrap text-sm text-brand-900/80">
                {item.description}
              </p>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function EducationPanel({
  items,
  compact = false,
}: {
  items: Array<EducationEntry & { id: number }>;
  compact?: boolean;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-brand-300">No education provided.</p>;
  }
  return (
    <div className={cn("space-y-4", compact && "space-y-3")}>
      {items.map((item) => {
        const years = formatYears(item.start_year, item.end_year);
        return (
          <div
            key={item.id}
            className={cn(
              !compact && "rounded-xl border border-brand-200/70 bg-[#f7faf9] p-4"
            )}
          >
            <p className="text-sm font-semibold text-brand-900">{item.institution}</p>
            <p className="mt-0.5 text-[13px] text-brand-300">
              {[item.degree, item.field_of_study, years].filter(Boolean).join(" · ")}
            </p>
          </div>
        );
      })}
    </div>
  );
}

function QuestionsPanel({
  answers,
  compact = false,
}: {
  answers: ApplicationDetail["answers"];
  compact?: boolean;
}) {
  if (answers.length === 0) {
    return <p className="text-sm text-brand-300">No questions for this job.</p>;
  }
  return (
    <div className={cn("space-y-4", compact && "space-y-3")}>
      {answers.map((answer) => (
        <div
          key={answer.question_id}
          className={cn(
            !compact && "rounded-xl border border-brand-200/70 bg-[#f7faf9] p-4"
          )}
        >
          <p className="text-sm font-semibold text-brand-900">{answer.prompt}</p>
          <p className="mt-1 whitespace-pre-wrap text-sm text-brand-900/80">
            {answer.value || "—"}
          </p>
        </div>
      ))}
    </div>
  );
}

function DocumentsPanel({
  cv,
  cover,
  preview,
  actingId,
  onView,
  onDownload,
  onClosePreview,
}: {
  cv?: ApplicationDocument;
  cover?: ApplicationDocument;
  preview: { document: ApplicationDocument; url: string } | null;
  actingId: number | null;
  onView: (document: ApplicationDocument) => void;
  onDownload: (document: ApplicationDocument) => void;
  onClosePreview: () => void;
}) {
  const docs = [cv, cover].filter(Boolean) as ApplicationDocument[];
  if (docs.length === 0) {
    return <p className="text-sm text-brand-300">No CV or cover letter uploaded.</p>;
  }
  return (
    <div className="space-y-4">
      {docs.map((document) => (
        <div
          key={document.id}
          className="flex flex-col gap-3 rounded-xl border border-brand-200/70 bg-[#f7faf9] p-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <p className="text-sm font-semibold text-brand-900">
              {document.kind === "cv" ? "CV" : "Cover letter"}
            </p>
            <p className="text-[13px] text-brand-300">{document.original_filename}</p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={actingId === document.id}
              onClick={() => void onView(document)}
              className="inline-flex h-9 items-center rounded-lg border border-brand-200 bg-white px-3 text-xs font-semibold text-brand-700 hover:bg-white disabled:opacity-50"
            >
              {actingId === document.id ? "Loading..." : "View"}
            </button>
            <button
              type="button"
              disabled={actingId === document.id}
              onClick={() => void onDownload(document)}
              className="inline-flex h-9 items-center rounded-lg border border-brand-200 bg-white px-3 text-xs font-semibold text-brand-700 hover:bg-white disabled:opacity-50"
            >
              Download
            </button>
          </div>
        </div>
      ))}
      {preview ? (
        <PreviewBlock preview={preview} onClose={onClosePreview} />
      ) : null}
    </div>
  );
}

function FilesPanel({
  documents,
  actingId,
  onView,
  onDownload,
  preview,
  onClosePreview,
}: {
  documents: ApplicationDocument[];
  actingId: number | null;
  onView: (document: ApplicationDocument) => void;
  onDownload: (document: ApplicationDocument) => void;
  preview: { document: ApplicationDocument; url: string } | null;
  onClosePreview: () => void;
}) {
  if (documents.length === 0) {
    return <p className="text-sm text-brand-300">No documents uploaded.</p>;
  }
  return (
    <div className="space-y-4" id="documents">
      {documents.map((document) => (
        <div
          key={document.id}
          className="flex flex-col gap-3 rounded-xl border border-brand-200/70 bg-[#f7faf9] p-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <p className="text-sm text-brand-900">
            <span className="font-semibold">
              {document.kind === "cv" ? "CV" : "Cover letter"}:
            </span>{" "}
            {document.original_filename}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={actingId === document.id}
              onClick={() => void onView(document)}
              className="text-sm font-semibold text-brand-700 disabled:opacity-50"
            >
              {actingId === document.id ? "Loading..." : "View"}
            </button>
            <button
              type="button"
              disabled={actingId === document.id}
              onClick={() => void onDownload(document)}
              className="text-sm font-semibold text-brand-700 disabled:opacity-50"
            >
              Download
            </button>
          </div>
        </div>
      ))}
      {preview ? (
        <PreviewBlock preview={preview} onClose={onClosePreview} />
      ) : null}
    </div>
  );
}

function InterviewsPanel({
  interviews,
  outcomeActingId,
  meetingRetryId,
  hireConfirmId,
  onRetryMeeting,
  onOutcome,
  onAskHire,
}: {
  interviews: InterviewSummary[];
  outcomeActingId: number | null;
  meetingRetryId: number | null;
  hireConfirmId: number | null;
  onRetryMeeting: (id: number) => void;
  onOutcome: (id: number, outcome: InterviewOutcome) => void;
  onAskHire: (id: number | null) => void;
}) {
  if (interviews.length === 0) {
    return <p className="text-sm text-brand-300">No interviews yet.</p>;
  }

  return (
    <ul className="space-y-4">
      {interviews.map((interview) => (
        <li
          key={interview.id}
          className="space-y-3 rounded-xl border border-brand-200/70 bg-[#f7faf9] p-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-brand-900">
              {interview.status_label}
            </p>
            <p className="text-xs text-brand-300">
              Created {formatDate(interview.created_at)}
            </p>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Detail label="Candidate" value={interview.candidate_name} />
            <Detail label="Job" value={interview.job_title} />
            <Detail
              label="Interviewers"
              value={
                interview.interviewers && interview.interviewers.length > 0
                  ? interview.interviewers
                      .map((item) =>
                        item.is_primary
                          ? `${item.full_name} (primary)`
                          : item.full_name
                      )
                      .join(", ")
                  : interview.interviewer_name || "—"
              }
            />
            <Detail label="Interview status" value={interview.status} />
          </div>
          {interview.message ? (
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
                HR message
              </p>
              <p className="mt-1 whitespace-pre-wrap text-sm text-brand-900/85">
                {interview.message}
              </p>
            </div>
          ) : null}
          {interview.selected_slot ? (
            <p className="text-sm text-brand-700">
              Scheduled:{" "}
              {formatSlotRange(
                interview.selected_slot.starts_at,
                interview.selected_slot.ends_at
              )}
            </p>
          ) : interview.status === "proposed" &&
            (interview.slot_count ?? 0) === 0 ? (
            <p className="text-sm text-brand-300">
              Waiting for primary interviewer to propose slots.
            </p>
          ) : (
            <p className="text-sm text-brand-300">
              Waiting for candidate to choose a slot.
            </p>
          )}

          <MeetingJoinBlock
            status={interview.status}
            meetingUrl={interview.meeting_url}
            showRetry={interview.status === "scheduled" && !interview.meeting_url}
            retrying={meetingRetryId === interview.id}
            onRetry={() => void onRetryMeeting(interview.id)}
          />

          {interview.status === "completed" ? (
            <div className="space-y-3 border-t border-brand-200/70 pt-3">
              {interview.completed_at ? (
                <Detail
                  label="Completed"
                  value={formatDate(interview.completed_at)}
                />
              ) : null}
              {interview.evaluation ? (
                <div className="space-y-2 text-sm">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
                    Evaluation
                  </p>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <Detail
                      label="Technical knowledge"
                      value={`${interview.evaluation.tech_knowledge ?? "—"}/5`}
                    />
                    <Detail
                      label="Communication"
                      value={`${interview.evaluation.communication ?? "—"}/5`}
                    />
                    <Detail
                      label="Problem solving"
                      value={`${interview.evaluation.problem_solving ?? "—"}/5`}
                    />
                    <Detail
                      label="Relevant experience"
                      value={`${interview.evaluation.relevant_experience ?? "—"}/5`}
                    />
                  </div>
                  {interview.evaluation.strengths ? (
                    <div>
                      <p className="text-xs text-brand-300">Strengths</p>
                      <p className="mt-1 whitespace-pre-wrap text-brand-900/85">
                        {interview.evaluation.strengths}
                      </p>
                    </div>
                  ) : null}
                  {interview.evaluation.weaknesses ? (
                    <div>
                      <p className="text-xs text-brand-300">Areas for improvement</p>
                      <p className="mt-1 whitespace-pre-wrap text-brand-900/85">
                        {interview.evaluation.weaknesses}
                      </p>
                    </div>
                  ) : null}
                  <Detail
                    label="Recommendation"
                    value={
                      interview.evaluation.recommendation_label ||
                      interview.evaluation.recommendation ||
                      "—"
                    }
                  />
                </div>
              ) : null}
              {!interview.evaluation && interview.feedback ? (
                <div>
                  <p className="text-xs text-brand-300">Feedback</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-brand-900/85">
                    {interview.feedback}
                  </p>
                </div>
              ) : null}
              {interview.outcome ? (
                <Detail
                  label="Outcome"
                  value={interview.outcome_label || interview.outcome}
                />
              ) : (
                <div className="space-y-3">
                  <p className="text-sm font-semibold text-brand-900">Outcome</p>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={outcomeActingId === interview.id}
                      onClick={() => void onOutcome(interview.id, "rejected")}
                      className="rounded-lg border border-rose-200 bg-white px-3 py-2 text-sm font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-50"
                    >
                      Reject
                    </button>
                    <button
                      type="button"
                      disabled={outcomeActingId === interview.id}
                      onClick={() =>
                        void onOutcome(interview.id, "another_interview")
                      }
                      className="rounded-lg border border-amber-200 bg-white px-3 py-2 text-sm font-medium text-amber-800 hover:bg-amber-50 disabled:opacity-50"
                    >
                      Another interview
                    </button>
                    <button
                      type="button"
                      disabled={outcomeActingId === interview.id}
                      onClick={() => onAskHire(interview.id)}
                      className="rounded-lg border border-emerald-200 bg-white px-3 py-2 text-sm font-medium text-emerald-800 hover:bg-emerald-50 disabled:opacity-50"
                    >
                      Hire
                    </button>
                  </div>
                  {hireConfirmId === interview.id ? (
                    <div className="space-y-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3">
                      <p className="text-sm text-emerald-900">
                        Are you sure you want to hire this candidate? This will mark
                        the application as hired and create an employee record.
                      </p>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          disabled={outcomeActingId === interview.id}
                          onClick={() => onAskHire(null)}
                          className="rounded-lg border border-brand-200 bg-white px-3 py-2 text-sm font-medium text-brand-700 disabled:opacity-50"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          disabled={outcomeActingId === interview.id}
                          onClick={() => void onOutcome(interview.id, "hired")}
                          className="rounded-lg bg-emerald-700 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-50"
                        >
                          {outcomeActingId === interview.id
                            ? "Hiring..."
                            : "Confirm hire"}
                        </button>
                      </div>
                    </div>
                  ) : null}
                </div>
              )}
              {interview.outcome === "hired" && interview.hired_employee_id ? (
                <Link
                  href={`/hr/employees/${interview.hired_employee_id}`}
                  className="inline-flex text-sm font-semibold text-brand-700 hover:text-brand-800"
                >
                  View employee
                </Link>
              ) : null}
            </div>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function PreviewBlock({
  preview,
  onClose,
}: {
  preview: { document: ApplicationDocument; url: string };
  onClose: () => void;
}) {
  return (
    <div className="space-y-3 rounded-xl border border-brand-200/70 p-4">
      <div className="flex items-start justify-between gap-4">
        <p className="text-sm font-semibold text-brand-900">
          {preview.document.original_filename}
        </p>
        <button
          type="button"
          onClick={onClose}
          className="text-sm font-medium text-brand-300 hover:text-brand-700"
        >
          Close
        </button>
      </div>
      {isPdf(preview.document) && preview.url ? (
        <iframe
          title={preview.document.original_filename}
          src={preview.url}
          className="h-[70vh] w-full rounded-lg border border-brand-200 bg-[#f7faf9]"
        />
      ) : (
        <p className="text-sm text-brand-300">
          In-browser preview is available for PDF files. Use Download to open this
          document.
        </p>
      )}
    </div>
  );
}

function FitScoreRing({ score }: { score: number }) {
  const clamped = Math.max(0, Math.min(100, score));
  const color = fitRingColor(clamped);
  const size = 112;
  const stroke = 8;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <div
      className="relative mx-auto shrink-0 sm:mx-0"
      style={{ width: size, height: size }}
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
        <span className="text-2xl font-bold tabular-nums text-brand-900">
          {Math.round(clamped)}
        </span>
        <span className="mt-1 text-[11px] font-medium text-brand-300">/ 100</span>
      </div>
    </div>
  );
}

function SkillBar({ label, value }: { label: string; value: number }) {
  const color =
    value < 30 ? "bg-red-500" : value < 60 ? "bg-orange-500" : "bg-emerald-500";
  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-2">
        <p className="text-[12px] font-medium text-brand-700">{label}</p>
        <p className="text-[12px] font-semibold tabular-nums text-brand-900">
          {value}%
        </p>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-brand-100">
        <div
          className={cn("h-full rounded-full transition-all", color)}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: ApplicationStatus }) {
  const pill = STATUS_PILL[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold",
        pill.wrap
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", pill.dot)} />
      {pill.label}
    </span>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
        {label}
      </p>
      <p className="mt-1 text-sm font-medium text-brand-900">{value}</p>
    </div>
  );
}

function InfoLine({ label, value }: { label: string; value: string }) {
  return (
    <p className="text-[13px] text-brand-700">
      <span className="text-brand-300">{label}: </span>
      {value}
    </p>
  );
}

function Banner({
  children,
  tone,
  icon,
}: {
  children: ReactNode;
  tone: "green" | "amber" | "red";
  icon?: ReactNode;
}) {
  const styles = {
    green: "border-emerald-200 bg-emerald-50 text-emerald-900",
    amber: "border-amber-200 bg-amber-50 text-amber-900",
    red: "border-red-200 bg-red-50 text-red-800",
  };
  return (
    <div
      className={cn(
        "flex items-start gap-2 border-t px-5 py-3 text-sm",
        styles[tone]
      )}
    >
      {icon ? <span className="mt-0.5 shrink-0">{icon}</span> : null}
      <div>{children}</div>
    </div>
  );
}

function AccordionRow({
  icon,
  title,
  count,
  open,
  onToggle,
  children,
  last = false,
}: {
  icon: ReactNode;
  title: string;
  count: string;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
  last?: boolean;
}) {
  return (
    <div className={cn(!last && "border-b border-brand-200/70")}>
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition hover:bg-[#f7faf9]"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#f3f6f5] text-brand-700">
          {icon}
        </span>
        <span className="min-w-0 flex-1 text-sm font-semibold text-brand-900">
          {title}
        </span>
        <span className="text-[12px] text-brand-300">{count}</span>
        <ChevronDown
          className={cn(
            "size-4 text-brand-300 transition-transform",
            open && "rotate-180"
          )}
        />
      </button>
      {open ? <div className="px-4 pb-4">{children}</div> : null}
    </div>
  );
}

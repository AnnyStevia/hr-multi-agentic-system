"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ApplicationSection } from "@/components/ApplicationSection";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { formatSlotRange, hasActiveInterviewInvitation } from "@/lib/interviews";
import type {
  ApplicationDetail,
  ApplicationDocument,
  ApplicationStatus,
  EducationEntry,
  ExperienceEntry,
} from "@/types/applications";
import type { InterviewOutcome, InterviewSummary } from "@/types/interviews";

const STATUS_ACTIONS: Partial<
  Record<ApplicationStatus, Array<{ value: ApplicationStatus; label: string; className: string }>>
> = {
  submitted: [
    {
      value: "screening",
      label: "Move to Screening",
      className: "bg-amber-500 text-white border-amber-500 hover:bg-amber-600",
    },
    {
      value: "rejected",
      label: "Reject",
      className: "bg-white text-red-700 border-red-200 hover:bg-red-50",
    },
  ],
  screening: [
    {
      value: "shortlisted",
      label: "Shortlist",
      className: "bg-blue-600 text-white border-blue-600 hover:bg-blue-700",
    },
    {
      value: "rejected",
      label: "Reject",
      className: "bg-white text-red-700 border-red-200 hover:bg-red-50",
    },
  ],
};

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
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

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="mt-0.5 text-sm text-gray-900">{value}</p>
    </div>
  );
}

function EducationRow({ item }: { item: EducationEntry }) {
  const years = formatYears(item.start_year, item.end_year);
  return (
    <div>
      <p className="text-sm text-gray-900">{item.institution}</p>
      <p className="text-sm text-gray-600">
        {[item.degree, item.field_of_study, years].filter(Boolean).join(" · ")}
      </p>
    </div>
  );
}

function ExperienceRow({ item, recent }: { item: ExperienceEntry; recent: boolean }) {
  const years = formatYears(item.start_year, item.end_year);
  return (
    <div>
      <p className="text-sm text-gray-900">
        {item.title} · {item.company}
        {recent ? <span className="ml-2 text-xs font-medium text-gray-500">Most recent</span> : null}
      </p>
      {years && <p className="text-sm text-gray-600">{years}</p>}
      {item.description && <p className="text-sm text-gray-600 whitespace-pre-wrap">{item.description}</p>}
    </div>
  );
}

export default function ApplicationDetailPage() {
  const params = useParams<{ id: string }>();
  const applicationId = Number(params.id);
  const [application, setApplication] = useState<ApplicationDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<number | null>(null);
  const [preview, setPreview] = useState<{ document: ApplicationDocument; url: string } | null>(null);
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [interviews, setInterviews] = useState<InterviewSummary[]>([]);
  const [interviewsError, setInterviewsError] = useState("");
  const [outcomeActingId, setOutcomeActingId] = useState<number | null>(null);
  const [hireConfirmId, setHireConfirmId] = useState<number | null>(null);
  const [successMessage, setSuccessMessage] = useState("");

  const loadInterviews = async () => {
    try {
      setInterviewsError("");
      setInterviews(await api.listApplicationInterviews(applicationId));
    } catch (err) {
      setInterviews([]);
      setInterviewsError(err instanceof Error ? err.message : "Failed to load interviews");
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
      load();
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
        return;
      }
      const result = await api.getApplicationDocumentUrl(applicationId, document.id, false);
      setPreview({ document, url: result.url });
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
      const result = await api.getApplicationDocumentUrl(applicationId, document.id, true);
      window.open(result.url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download document");
    } finally {
      setActingId(null);
    }
  };

  const changeStatus = async (status: ApplicationStatus) => {
    if (!application || status === application.status) {
      return;
    }
    setUpdatingStatus(true);
    setError("");
    try {
      const updated = await api.updateApplicationStatus(applicationId, status);
      setApplication(updated);
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
      const updatedInterview = await api.recordInterviewOutcome(interviewId, { outcome });
      setHireConfirmId(null);
      setApplication(await api.getApplication(applicationId));
      await loadInterviews();
      if (outcome === "hired") {
        setSuccessMessage(
          updatedInterview.hired_employee_id
            ? "Candidate hired. Employee record created."
            : "Candidate hired.",
        );
      } else if (outcome === "rejected") {
        setSuccessMessage("Candidate rejected. Application status updated.");
      } else {
        setSuccessMessage("Marked for another interview. You can send a new invitation.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record outcome");
    } finally {
      setOutcomeActingId(null);
    }
  };

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!application) {
    return <p className="text-red-700">{error || "Application not found"}</p>;
  }

  const actions = STATUS_ACTIONS[application.status] ?? [];
  const experience = sortExperience(application.experience);
  const hasPendingInvitation = interviews.some((interview) => interview.status === "proposed");
  const hasActiveInvitation = hasActiveInterviewInvitation(interviews);
  const hasPendingOutcome = interviews.some(
    (interview) => interview.status === "completed" && !interview.outcome,
  );
  const hiredEmployeeId = interviews.find((interview) => interview.hired_employee_id)?.hired_employee_id ?? null;

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <Link href={`/hr/jobs/${application.job.id}/applications`} className="text-sm text-gray-500 hover:text-gray-800">
          Applications
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900">{application.candidate.full_name}</h1>
          <StatusBadge status={application.status} />
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}
      {successMessage && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg text-sm">
          {successMessage}
        </div>
      )}

      <ApplicationSection title="Candidate">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Detail label="First name" value={application.candidate.first_name} />
          <Detail label="Last name" value={application.candidate.last_name} />
          <Detail label="Email" value={application.candidate.email} />
          <Detail label="Phone" value={application.candidate.phone || "—"} />
        </div>
      </ApplicationSection>

      <ApplicationSection title="Application">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Detail label="Job title" value={application.job.title} />
          <Detail label="Department" value={application.job.department || "—"} />
          <Detail label="Application date" value={formatDate(application.submitted_at)} />
          <div>
            <p className="text-xs text-gray-500">Status</p>
            <div className="mt-1">
              <StatusBadge status={application.status} />
            </div>
          </div>
        </div>
        {application.status === "hired" && hiredEmployeeId ? (
          <div className="pt-4 border-t border-gray-100">
            <p className="text-sm text-green-800 mb-2">Employee created.</p>
            <Link
              href={`/hr/employees/${hiredEmployeeId}`}
              className="inline-flex text-sm font-medium text-brand-700 hover:text-brand-800"
            >
              View employee record
            </Link>
          </div>
        ) : null}
        {actions.length > 0 ? (
          <div className="pt-2">
            <p className="text-sm font-medium text-gray-700 mb-2">Change status</p>
            <div className="flex flex-wrap gap-2">
              {actions.map((action) => (
                <button
                  key={action.value}
                  type="button"
                  disabled={updatingStatus}
                  onClick={() => changeStatus(action.value)}
                  className={`px-3 py-2 rounded-lg text-sm font-medium border transition disabled:opacity-50 ${action.className}`}
                >
                  {action.label}
                </button>
              ))}
            </div>
            {updatingStatus && <p className="mt-2 text-xs text-gray-500">Updating status…</p>}
          </div>
        ) : (
          <p className="text-sm text-gray-500">No further status changes are available.</p>
        )}
        {application.status === "shortlisted" && !hasActiveInvitation && (
          <div className="pt-4 border-t border-gray-100">
            <Link
              href={`/hr/applications/${applicationId}/invite`}
              className="inline-flex bg-brand-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brand-700"
            >
              Invite to interview
            </Link>
          </div>
        )}
        {hasPendingInvitation && (
          <div className="pt-4 border-t border-gray-100 text-sm text-amber-800 bg-amber-50 border border-amber-200 px-4 py-3 rounded-lg space-y-2">
            <p>
              {interviews.some((interview) => interview.status === "proposed" && (interview.slot_count ?? 0) === 0)
                ? "Waiting for the primary interviewer to propose available slots."
                : "Waiting for the candidate to choose a slot."}
            </p>
            {interviews.some((interview) => interview.status === "proposed" && (interview.slot_count ?? 0) === 0) && (
              <p>
                If you are the primary interviewer, open{" "}
                <Link href="/employee/interviews" className="font-medium underline underline-offset-2">
                  My interviews
                </Link>{" "}
                (also in the HR sidebar) to submit availability.
              </p>
            )}
          </div>
        )}
        {!hasPendingInvitation && hasActiveInvitation && !hasPendingOutcome && (
          <p className="pt-4 border-t border-gray-100 text-sm text-green-800 bg-green-50 border border-green-200 px-4 py-3 rounded-lg">
            Interview is scheduled. A new invitation cannot be created until this interview is completed or cancelled.
          </p>
        )}
        {hasPendingOutcome && (
          <p className="pt-4 border-t border-gray-100 text-sm text-amber-800 bg-amber-50 border border-amber-200 px-4 py-3 rounded-lg">
            Interview completed. Record an outcome before inviting again.
          </p>
        )}
        {interviewsError && (
          <p className="pt-4 border-t border-gray-100 text-sm text-red-700 bg-red-50 border border-red-200 px-4 py-3 rounded-lg">
            {interviewsError}
          </p>
        )}
      </ApplicationSection>

      <ApplicationSection title="Fit assessment">
        {application.fit_assessment ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-baseline gap-3">
              <p className="text-3xl font-semibold text-gray-900">
                {application.fit_assessment.fit_score}
                <span className="text-lg font-normal text-gray-500"> / 100</span>
              </p>
              <p className="text-sm font-medium text-gray-700">
                {application.fit_assessment.fit_level === "GOOD"
                  ? "GOOD MATCH"
                  : application.fit_assessment.fit_level === "MEDIUM"
                    ? "MEDIUM MATCH"
                    : application.fit_assessment.fit_level === "BAD"
                      ? "WEAK MATCH"
                      : application.fit_assessment.fit_level}
              </p>
            </div>
            {application.fit_assessment.matching_skills.length > 0 && (
              <div>
                <p className="text-xs text-gray-500 mb-1">Matching skills</p>
                <ul className="space-y-1">
                  {application.fit_assessment.matching_skills.map((skill) => (
                    <li key={skill} className="text-sm text-gray-900">
                      ✓ {skill}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {application.fit_assessment.missing_skills.length > 0 && (
              <div>
                <p className="text-xs text-gray-500 mb-1">Missing / not identified</p>
                <ul className="space-y-1">
                  {application.fit_assessment.missing_skills.map((skill) => (
                    <li key={skill} className="text-sm text-gray-700">
                      • {skill}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {application.fit_assessment.experience_match && (
              <Detail label="Experience" value={application.fit_assessment.experience_match} />
            )}
            {application.fit_assessment.education_match && (
              <Detail label="Education" value={application.fit_assessment.education_match} />
            )}
            {application.fit_assessment.explanation && (
              <div>
                <p className="text-xs text-gray-500 mb-1">AI assessment</p>
                <p className="text-sm text-gray-800 whitespace-pre-wrap">
                  {application.fit_assessment.explanation}
                </p>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-gray-500">Analysis pending. Refresh shortly after a new application.</p>
        )}
      </ApplicationSection>

      {interviews.length > 0 && (
        <ApplicationSection title="Interviews" collapsible defaultOpen={false}>
          <ul className="space-y-4">
            {interviews.map((interview) => (
              <li key={interview.id} className="rounded-lg border border-gray-200 px-4 py-4 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium text-gray-900">{interview.status_label}</p>
                  <p className="text-xs text-gray-500">Created {formatDate(interview.created_at)}</p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                  <Detail label="Candidate" value={interview.candidate_name} />
                  <Detail label="Job" value={interview.job_title} />
                  <Detail
                    label="Interviewers"
                    value={
                      interview.interviewers && interview.interviewers.length > 0
                        ? interview.interviewers
                            .map((item) =>
                              item.is_primary ? `${item.full_name} (primary)` : item.full_name,
                            )
                            .join(", ")
                        : interview.interviewer_name || "—"
                    }
                  />
                  <Detail label="Interview status" value={interview.status} />
                </div>
                {interview.message ? (
                  <div>
                    <p className="text-xs text-gray-500">HR message</p>
                    <p className="mt-1 text-sm text-gray-800 whitespace-pre-wrap">{interview.message}</p>
                  </div>
                ) : null}
                {interview.selected_slot ? (
                  <p className="text-sm text-gray-700">
                    Scheduled: {formatSlotRange(interview.selected_slot.starts_at, interview.selected_slot.ends_at)}
                  </p>
                ) : interview.status === "proposed" && (interview.slot_count ?? 0) === 0 ? (
                  <p className="text-sm text-gray-600">Waiting for primary interviewer to propose slots.</p>
                ) : (
                  <p className="text-sm text-gray-600">Waiting for candidate to choose a slot.</p>
                )}

                {interview.status === "completed" && (
                  <div className="space-y-3 border-t border-gray-100 pt-3">
                    {interview.completed_at && (
                      <Detail label="Completed" value={formatDate(interview.completed_at)} />
                    )}
                    {interview.evaluation && (
                      <div className="space-y-2 text-sm">
                        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Evaluation</p>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          <Detail label="Technical knowledge" value={`${interview.evaluation.tech_knowledge ?? "—"}/5`} />
                          <Detail label="Communication" value={`${interview.evaluation.communication ?? "—"}/5`} />
                          <Detail label="Problem solving" value={`${interview.evaluation.problem_solving ?? "—"}/5`} />
                          <Detail label="Relevant experience" value={`${interview.evaluation.relevant_experience ?? "—"}/5`} />
                        </div>
                        {interview.evaluation.strengths && (
                          <div>
                            <p className="text-xs text-gray-500">Strengths</p>
                            <p className="mt-1 text-gray-800 whitespace-pre-wrap">{interview.evaluation.strengths}</p>
                          </div>
                        )}
                        {interview.evaluation.weaknesses && (
                          <div>
                            <p className="text-xs text-gray-500">Areas for improvement</p>
                            <p className="mt-1 text-gray-800 whitespace-pre-wrap">{interview.evaluation.weaknesses}</p>
                          </div>
                        )}
                        {interview.evaluation.additional_comments && (
                          <div>
                            <p className="text-xs text-gray-500">Additional comments</p>
                            <p className="mt-1 text-gray-800 whitespace-pre-wrap">
                              {interview.evaluation.additional_comments}
                            </p>
                          </div>
                        )}
                        <Detail
                          label="Recommendation"
                          value={
                            interview.evaluation.recommendation_label ||
                            interview.evaluation.recommendation ||
                            "—"
                          }
                        />
                      </div>
                    )}
                    {!interview.evaluation && interview.feedback && (
                      <div>
                        <p className="text-xs text-gray-500">Feedback</p>
                        <p className="mt-1 text-sm text-gray-800 whitespace-pre-wrap">{interview.feedback}</p>
                      </div>
                    )}
                    {interview.outcome ? (
                      <Detail label="Outcome" value={interview.outcome_label || interview.outcome} />
                    ) : (
                      <div className="space-y-3">
                        <p className="text-sm font-medium text-gray-800">Outcome</p>
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            disabled={outcomeActingId === interview.id}
                            onClick={() => submitOutcome(interview.id, "rejected")}
                            className="px-3 py-2 rounded-lg text-sm font-medium border border-red-200 text-red-700 bg-white hover:bg-red-50 disabled:opacity-50"
                          >
                            Reject
                          </button>
                          <button
                            type="button"
                            disabled={outcomeActingId === interview.id}
                            onClick={() => submitOutcome(interview.id, "another_interview")}
                            className="px-3 py-2 rounded-lg text-sm font-medium border border-amber-200 text-amber-800 bg-white hover:bg-amber-50 disabled:opacity-50"
                          >
                            Another interview
                          </button>
                          <button
                            type="button"
                            disabled={outcomeActingId === interview.id}
                            onClick={() => setHireConfirmId(interview.id)}
                            className="px-3 py-2 rounded-lg text-sm font-medium border border-green-200 text-green-800 bg-white hover:bg-green-50 disabled:opacity-50"
                          >
                            Hire
                          </button>
                        </div>
                        {hireConfirmId === interview.id && (
                          <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 space-y-3">
                            <p className="text-sm text-green-900">
                              Are you sure you want to hire this candidate? This will mark the application as
                              HIRED and create an employee record.
                            </p>
                            <div className="flex flex-wrap gap-2">
                              <button
                                type="button"
                                disabled={outcomeActingId === interview.id}
                                onClick={() => setHireConfirmId(null)}
                                className="px-3 py-2 rounded-lg text-sm font-medium border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                              >
                                Cancel
                              </button>
                              <button
                                type="button"
                                disabled={outcomeActingId === interview.id}
                                onClick={() => submitOutcome(interview.id, "hired")}
                                className="px-3 py-2 rounded-lg text-sm font-medium bg-green-700 text-white hover:bg-green-800 disabled:opacity-50"
                              >
                                {outcomeActingId === interview.id ? "Hiring..." : "Confirm hire"}
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                    {interview.outcome === "hired" && interview.hired_employee_id ? (
                      <Link
                        href={`/hr/employees/${interview.hired_employee_id}`}
                        className="inline-flex text-sm font-medium text-brand-700 hover:text-brand-800"
                      >
                        View employee
                      </Link>
                    ) : null}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </ApplicationSection>
      )}

      <ApplicationSection title="Education" collapsible defaultOpen={false}>
        {application.education.length === 0 ? (
          <p className="text-sm text-gray-500">No education provided.</p>
        ) : (
          application.education.map((item) => <EducationRow key={item.id} item={item} />)
        )}
      </ApplicationSection>

      <ApplicationSection title="Experience" collapsible defaultOpen={false}>
        {experience.length === 0 ? (
          <p className="text-sm text-gray-500">No experience provided.</p>
        ) : (
          experience.map((item, index) => (
            <ExperienceRow key={item.id} item={item} recent={index === 0} />
          ))
        )}
      </ApplicationSection>

      <ApplicationSection title="Questions and answers" collapsible defaultOpen={false}>
        {application.answers.length === 0 ? (
          <p className="text-sm text-gray-500">No questions for this job.</p>
        ) : (
          application.answers.map((answer) => (
            <div key={answer.question_id}>
              <p className="text-sm font-medium text-gray-800">{answer.prompt}</p>
              <p className="text-sm text-gray-600 whitespace-pre-wrap">{answer.value || "—"}</p>
            </div>
          ))
        )}
      </ApplicationSection>

      <ApplicationSection title="Documents" collapsible defaultOpen={false}>
        <div id="documents" className="space-y-3">
          {application.documents.map((document) => (
            <div key={document.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <p className="text-sm text-gray-800">
                {document.kind === "cv" ? "CV" : "Cover letter"}: {document.original_filename}
              </p>
              <div className="flex gap-3">
                <button
                  type="button"
                  disabled={actingId === document.id}
                  onClick={() => viewDocument(document)}
                  className="text-sm text-brand-700 disabled:opacity-50"
                >
                  {actingId === document.id ? "Loading..." : document.kind === "cv" ? "View CV" : "View Cover Letter"}
                </button>
                <button
                  type="button"
                  disabled={actingId === document.id}
                  onClick={() => downloadDocument(document)}
                  className="text-sm text-gray-700 disabled:opacity-50"
                >
                  Download
                </button>
              </div>
            </div>
          ))}
        </div>
      </ApplicationSection>

      {preview && (
        <ApplicationSection title={preview.document.kind === "cv" ? "CV preview" : "Cover letter preview"}>
          <div className="flex items-start justify-between gap-4">
            <p className="text-sm text-gray-800">{preview.document.original_filename}</p>
            <button type="button" onClick={() => setPreview(null)} className="text-sm text-gray-600">
              Close
            </button>
          </div>
          {isPdf(preview.document) && preview.url ? (
            <iframe
              title={preview.document.original_filename}
              src={preview.url}
              className="w-full h-[80vh] rounded-lg border border-gray-200 bg-gray-50"
            />
          ) : (
            <p className="text-sm text-gray-600">
              In-browser preview is available for PDF files. This document is{" "}
              {preview.document.original_filename.split(".").pop()?.toUpperCase() || "not a PDF"}. Use
              Download to open it.
            </p>
          )}
        </ApplicationSection>
      )}
    </div>
  );
}

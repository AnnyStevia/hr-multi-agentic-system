"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { MeetingJoinBlock } from "@/components/MeetingJoinBlock";
import { formatSlotDate, formatSlotTimeRange } from "@/lib/interviews";
import type { InterviewDetail } from "@/types/interviews";

const STATUS_LABELS: Record<string, string> = {
  proposed: "Awaiting your response",
  scheduled: "Scheduled",
  completed: "Interview completed",
  cancelled: "Cancelled",
};

export default function CandidateInterviewPage() {
  const params = useParams<{ id: string }>();
  const interviewId = Number(params.id);
  const [interview, setInterview] = useState<InterviewDetail | null>(null);
  const [selectedSlotId, setSelectedSlotId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        setInterview(await api.getCareerInterview(interviewId));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load interview invitation");
      } finally {
        setLoading(false);
      }
    };
    if (!Number.isNaN(interviewId)) {
      load();
    }
  }, [interviewId]);

  const handleConfirm = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedSlotId) {
      setError("Select one of the proposed time slots.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const confirmed = await api.confirmInterviewSlot(interviewId, { slot_id: selectedSlotId });
      setInterview(confirmed);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to confirm interview");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!interview) {
    return <p className="text-red-700">{error || "Interview invitation not found"}</p>;
  }

  const isScheduled = interview.status === "scheduled";
  const isCompleted = interview.status === "completed";
  const interviewers = interview.interviewers || [];

  return (
    <div className="space-y-6">
      <div>
        <Link href="/careers/jobs" className="text-sm text-gray-500 hover:text-gray-800">
          Careers
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">
          {isCompleted ? "Interview completed" : isScheduled ? "Interview confirmed" : "Interview invitation"}
        </h1>
        <p className="mt-1 text-sm text-gray-600">{interview.job_title}</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{error}</div>
      )}

      <div className="bg-white rounded-xl border shadow-sm p-6 space-y-5">
        {interviewers.length > 0 && (
          <div>
            <h2 className="text-sm font-medium text-gray-500">Interviewers</h2>
            <ul className="mt-2 space-y-1 text-sm text-gray-900">
              {interviewers.map((member) => (
                <li key={member.employee_id}>
                  {member.full_name}
                  {member.position ? ` — ${member.position}` : ""}
                </li>
              ))}
            </ul>
          </div>
        )}

        <MeetingJoinBlock status={interview.status} meetingUrl={interview.meeting_url} />

        {!isScheduled && !isCompleted && interview.message && (
          <div>
            <h2 className="text-sm font-medium text-gray-500">Message</h2>
            <p className="mt-2 text-sm text-gray-800 whitespace-pre-wrap">{interview.message}</p>
          </div>
        )}

        {isCompleted ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
              <p className="text-sm font-medium text-gray-900">Interview completed</p>
              <p className="mt-1 text-sm text-gray-700">
                This interview has been completed. Check your application status on the job page for updates.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-xs text-gray-500">Job</p>
                <p className="mt-0.5 text-gray-900">{interview.job_title}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Status</p>
                <p className="mt-0.5 text-gray-900">{STATUS_LABELS[interview.status] || interview.status}</p>
              </div>
              {interview.selected_slot ? (
                <>
                  <div>
                    <p className="text-xs text-gray-500">Date</p>
                    <p className="mt-0.5 text-gray-900">{formatSlotDate(interview.selected_slot.starts_at)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Time</p>
                    <p className="mt-0.5 text-gray-900">
                      {formatSlotTimeRange(interview.selected_slot.starts_at, interview.selected_slot.ends_at)}
                    </p>
                  </div>
                </>
              ) : null}
            </div>
          </div>
        ) : isScheduled && interview.selected_slot ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3">
              <p className="text-sm font-medium text-green-900">Interview confirmed</p>
              <p className="mt-1 text-sm text-green-800">Your interview time has been saved.</p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-xs text-gray-500">Job</p>
                <p className="mt-0.5 text-gray-900">{interview.job_title}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Status</p>
                <p className="mt-0.5 text-gray-900 capitalize">{STATUS_LABELS[interview.status] || interview.status}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Date</p>
                <p className="mt-0.5 text-gray-900">{formatSlotDate(interview.selected_slot.starts_at)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Time</p>
                <p className="mt-0.5 text-gray-900">
                  {formatSlotTimeRange(interview.selected_slot.starts_at, interview.selected_slot.ends_at)}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <form onSubmit={handleConfirm} className="space-y-4">
            <h2 className="text-sm font-medium text-gray-900">Available slots</h2>
            <p className="text-xs text-gray-500">Select one time that works for you.</p>
            <div className="space-y-3">
              {interview.slots.filter((slot) => slot.is_available).map((slot) => (
                <label
                  key={slot.id}
                  className={`flex items-start gap-3 rounded-lg border px-4 py-3 cursor-pointer ${
                    selectedSlotId === slot.id ? "border-brand-500 bg-brand-50" : "border-gray-200"
                  }`}
                >
                  <input
                    type="radio"
                    name="slot"
                    value={slot.id}
                    checked={selectedSlotId === slot.id}
                    onChange={() => setSelectedSlotId(slot.id)}
                    className="mt-1"
                  />
                  <span className="text-sm text-gray-800">
                    {formatSlotDate(slot.starts_at)} — {formatSlotTimeRange(slot.starts_at, slot.ends_at)}
                  </span>
                </label>
              ))}
            </div>
            <button
              type="submit"
              disabled={submitting || !selectedSlotId}
              className="bg-brand-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
            >
              {submitting ? "Confirming..." : "Confirm interview"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

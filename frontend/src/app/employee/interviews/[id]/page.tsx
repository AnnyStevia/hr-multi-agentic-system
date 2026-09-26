"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { formatSlotRange, toIsoFromDateAndTime } from "@/lib/interviews";
import type { InterviewDetail, InterviewerRecommendation } from "@/types/interviews";

const inputClass =
  "w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none";

type SlotForm = { date: string; startTime: string; endTime: string };

const emptySlot = (): SlotForm => ({ date: "", startTime: "", endTime: "" });

function canProposeSlots(interview: InterviewDetail): boolean {
  if (interview.can_propose_slots) return true;
  return (
    interview.my_role === "primary" &&
    interview.status === "proposed" &&
    (interview.slot_count ?? interview.slots?.length ?? 0) === 0
  );
}

export default function MyInterviewDetailPage() {
  const params = useParams<{ id: string }>();
  const interviewId = Number(params.id);
  const [interview, setInterview] = useState<InterviewDetail | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(true);
  const [slots, setSlots] = useState<SlotForm[]>([emptySlot(), emptySlot()]);
  const [submittingSlots, setSubmittingSlots] = useState(false);
  const [submittingComplete, setSubmittingComplete] = useState(false);
  const [techKnowledge, setTechKnowledge] = useState(3);
  const [communication, setCommunication] = useState(3);
  const [problemSolving, setProblemSolving] = useState(3);
  const [relevantExperience, setRelevantExperience] = useState(3);
  const [strengths, setStrengths] = useState("");
  const [weaknesses, setWeaknesses] = useState("");
  const [additionalComments, setAdditionalComments] = useState("");
  const [recommendation, setRecommendation] = useState<InterviewerRecommendation>("proceed");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setInterview(await api.getMyInterview(interviewId));
    } catch (err) {
      setInterview(null);
      setError(err instanceof Error ? err.message : "Failed to load interview");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!Number.isNaN(interviewId)) {
      load();
    }
  }, [interviewId]);

  const submitSlots = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (slots.some((slot) => !slot.date || !slot.startTime || !slot.endTime)) {
      setError("Complete all proposed slots.");
      return;
    }
    setSubmittingSlots(true);
    try {
      const updated = await api.proposeMyInterviewSlots(interviewId, {
        slots: slots.map((slot) => ({
          starts_at: toIsoFromDateAndTime(slot.date, slot.startTime),
          ends_at: toIsoFromDateAndTime(slot.date, slot.endTime),
        })),
      });
      setInterview(updated);
      setSuccess("Slots submitted. The candidate has been notified.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to propose slots");
    } finally {
      setSubmittingSlots(false);
    }
  };

  const submitComplete = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (!strengths.trim() || !weaknesses.trim()) {
      setError("Strengths and areas for improvement are required.");
      return;
    }
    setSubmittingComplete(true);
    try {
      const updated = await api.completeInterview(interviewId, {
        tech_knowledge: techKnowledge,
        communication,
        problem_solving: problemSolving,
        relevant_experience: relevantExperience,
        strengths: strengths.trim(),
        weaknesses: weaknesses.trim(),
        additional_comments: additionalComments.trim() || null,
        recommendation,
      });
      setInterview(updated);
      setSuccess("Interview completed. HR can now record a decision.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to complete interview");
    } finally {
      setSubmittingComplete(false);
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
    return <p className="text-red-700">{error || "Interview not found"}</p>;
  }

  const showProposeForm = canProposeSlots(interview);
  const showCompleteForm = Boolean(interview.can_complete);

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <Link href="/employee/interviews" className="text-sm text-gray-500 hover:text-gray-800">
          My interviews
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">Interview assignment</h1>
        <p className="mt-1 text-sm text-gray-600">{interview.status_label || interview.status}</p>
        {interview.my_role === "primary" && (
          <p className="mt-1 text-sm font-medium text-brand-700">You are the primary interviewer</p>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{error}</div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg text-sm">{success}</div>
      )}

      {showProposeForm && (
        <div className="rounded-xl border border-brand-300 bg-brand-50 px-4 py-3 text-sm text-brand-900">
          <p className="font-semibold">Action needed: propose time slots</p>
          <p className="mt-1 text-brand-800">
            Use the form below to offer 1–10 available times. The candidate is notified only after you submit.
          </p>
          <a href="#propose-slots" className="mt-2 inline-block font-medium text-brand-700 underline underline-offset-2">
            Go to propose slots form
          </a>
        </div>
      )}

      <div className="bg-white rounded-xl border shadow-sm p-6 space-y-4 text-sm">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <p className="text-xs text-gray-500">Candidate</p>
            <p className="mt-0.5 text-gray-900">{interview.candidate_name}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Position</p>
            <p className="mt-0.5 text-gray-900">{interview.job_title}</p>
          </div>
        </div>
        <div>
          <p className="text-xs text-gray-500">Panel</p>
          <ul className="mt-1 space-y-1">
            {(interview.interviewers || []).map((member) => (
              <li key={member.employee_id} className="text-gray-900">
                {member.is_primary ? "★ " : ""}
                {member.full_name}
                {member.position ? ` — ${member.position}` : ""}
                {member.is_primary ? " (primary)" : ""}
              </li>
            ))}
          </ul>
        </div>
        {interview.selected_slot && (
          <p className="text-gray-800">
            Scheduled: {formatSlotRange(interview.selected_slot.starts_at, interview.selected_slot.ends_at)}
          </p>
        )}
        {!showProposeForm && (interview.slots?.length ?? 0) > 0 && interview.status === "proposed" && (
          <div>
            <p className="text-xs text-gray-500 mb-1">Proposed slots (awaiting candidate)</p>
            <ul className="space-y-1 text-gray-800">
              {interview.slots.map((slot) => (
                <li key={slot.id}>{formatSlotRange(slot.starts_at, slot.ends_at)}</li>
              ))}
            </ul>
          </div>
        )}
        {interview.meeting_url && (
          <p>
            <a href={interview.meeting_url} className="text-brand-700 hover:underline" target="_blank" rel="noreferrer">
              Meeting link
            </a>
          </p>
        )}
      </div>

      {showProposeForm && (
        <form
          id="propose-slots"
          onSubmit={submitSlots}
          className="bg-white rounded-xl border-2 border-brand-400 shadow-sm p-6 space-y-4 scroll-mt-6"
        >
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Propose interview slots</h2>
            <p className="mt-1 text-sm text-gray-600">
              Add at least one future time window, then click{" "}
              <span className="font-medium">Submit availability</span>.
            </p>
          </div>
          {slots.map((slot, index) => (
            <div key={index} className="grid grid-cols-1 sm:grid-cols-3 gap-3 border border-gray-200 rounded-lg p-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Date</label>
                <input
                  type="date"
                  required
                  value={slot.date}
                  onChange={(e) =>
                    setSlots((current) =>
                      current.map((item, i) => (i === index ? { ...item, date: e.target.value } : item)),
                    )
                  }
                  className={inputClass}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Start</label>
                <input
                  type="time"
                  required
                  value={slot.startTime}
                  onChange={(e) =>
                    setSlots((current) =>
                      current.map((item, i) => (i === index ? { ...item, startTime: e.target.value } : item)),
                    )
                  }
                  className={inputClass}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">End</label>
                <input
                  type="time"
                  required
                  value={slot.endTime}
                  onChange={(e) =>
                    setSlots((current) =>
                      current.map((item, i) => (i === index ? { ...item, endTime: e.target.value } : item)),
                    )
                  }
                  className={inputClass}
                />
              </div>
            </div>
          ))}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setSlots((current) => (current.length >= 10 ? current : [...current, emptySlot()]))}
              className="px-3 py-2 rounded-lg border text-sm text-gray-700 hover:bg-gray-50"
            >
              Add another slot
            </button>
            <button
              type="button"
              disabled={slots.length <= 1}
              onClick={() => setSlots((current) => (current.length <= 1 ? current : current.slice(0, -1)))}
              className="px-3 py-2 rounded-lg border text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-40"
            >
              Remove last
            </button>
          </div>
          <button
            type="submit"
            disabled={submittingSlots}
            className="w-full sm:w-auto bg-brand-600 text-white px-5 py-3 rounded-lg text-sm font-semibold hover:bg-brand-700 disabled:opacity-50"
          >
            {submittingSlots ? "Submitting..." : "Submit availability"}
          </button>
        </form>
      )}

      {!showProposeForm &&
        interview.my_role === "panel" &&
        interview.status === "proposed" &&
        (interview.slot_count ?? 0) === 0 && (
          <div className="rounded-xl border bg-white px-4 py-3 text-sm text-gray-700">
            Waiting for the primary interviewer to propose available time slots.
          </div>
        )}

      {showCompleteForm && (
        <form onSubmit={submitComplete} className="bg-white rounded-xl border shadow-sm p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Complete interview</h2>
          {(
            [
              ["Technical knowledge", techKnowledge, setTechKnowledge],
              ["Communication", communication, setCommunication],
              ["Problem solving", problemSolving, setProblemSolving],
              ["Relevant experience", relevantExperience, setRelevantExperience],
            ] as const
          ).map(([label, value, setter]) => (
            <div key={label}>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {label}: {value}/5
              </label>
              <input
                type="range"
                min={1}
                max={5}
                value={value}
                onChange={(e) => setter(Number(e.target.value))}
                className="w-full"
              />
            </div>
          ))}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Strengths</label>
            <textarea required rows={3} value={strengths} onChange={(e) => setStrengths(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Areas for improvement</label>
            <textarea
              required
              rows={3}
              value={weaknesses}
              onChange={(e) => setWeaknesses(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Additional comments</label>
            <textarea
              rows={3}
              value={additionalComments}
              onChange={(e) => setAdditionalComments(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Recommendation</label>
            <select
              value={recommendation}
              onChange={(e) => setRecommendation(e.target.value as InterviewerRecommendation)}
              className={inputClass}
            >
              <option value="proceed">Proceed</option>
              <option value="additional_interview">Additional interview</option>
              <option value="do_not_proceed">Do not proceed</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={submittingComplete}
            className="bg-brand-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
          >
            {submittingComplete ? "Saving..." : "Submit feedback"}
          </button>
        </form>
      )}

      {interview.status === "completed" && interview.evaluation && interview.my_role === "primary" && (
        <div className="bg-white rounded-xl border shadow-sm p-6 space-y-2 text-sm">
          <h2 className="text-lg font-semibold text-gray-900">Submitted evaluation</h2>
          <p>Recommendation: {interview.evaluation.recommendation_label || interview.evaluation.recommendation}</p>
        </div>
      )}
    </div>
  );
}

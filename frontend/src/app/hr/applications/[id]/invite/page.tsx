"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ApplicationSection } from "@/components/ApplicationSection";
import { api } from "@/lib/api";
import { hasActiveInterviewInvitation, toIsoFromDateAndTime } from "@/lib/interviews";
import type { ApplicationDetail } from "@/types/applications";
import type { Employee } from "@/types/employees";

const inputClass =
  "w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition";

const MIN_SLOTS = 2;
const MAX_SLOTS = 5;

type SlotForm = {
  date: string;
  startTime: string;
  endTime: string;
};

const emptySlot = (): SlotForm => ({ date: "", startTime: "", endTime: "" });

export default function InviteToInterviewPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const applicationId = Number(params.id);
  const [application, setApplication] = useState<ApplicationDetail | null>(null);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [selectedInterviewerIds, setSelectedInterviewerIds] = useState<number[]>([]);
  const [message, setMessage] = useState("");
  const [slots, setSlots] = useState<SlotForm[]>([emptySlot(), emptySlot()]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const [data, employeeList] = await Promise.all([
          api.getApplication(applicationId),
          api.listEmployees({ status: "active" }),
        ]);
        setEmployees(employeeList.items);
        if (data.status !== "shortlisted") {
          setError("Interview invitations can only be created for shortlisted applications.");
        } else {
          const existing = await api.listApplicationInterviews(applicationId);
          if (existing.some((interview) => interview.status === "proposed")) {
            setError("An invitation is already waiting for the candidate's response.");
          } else if (existing.some((interview) => interview.status === "completed" && !interview.outcome)) {
            setError("Record an interview outcome before inviting again.");
          } else if (hasActiveInterviewInvitation(existing)) {
            setError("An interview is already scheduled for this application.");
          }
        }
        setApplication(data);
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

  const toggleInterviewer = (employeeId: number) => {
    setSelectedInterviewerIds((current) =>
      current.includes(employeeId)
        ? current.filter((id) => id !== employeeId)
        : [...current, employeeId],
    );
  };

  const updateSlot = (index: number, field: keyof SlotForm, value: string) => {
    setSlots((current) => current.map((slot, i) => (i === index ? { ...slot, [field]: value } : slot)));
  };

  const addSlot = () => {
    setSlots((current) => (current.length >= MAX_SLOTS ? current : [...current, emptySlot()]));
  };

  const removeSlot = (index: number) => {
    setSlots((current) => (current.length <= MIN_SLOTS ? current : current.filter((_, i) => i !== index)));
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (!message.trim()) {
      setError("Message is required.");
      return;
    }
    if (selectedInterviewerIds.length < 1) {
      setError("Select at least one interviewer.");
      return;
    }
    if (slots.length < MIN_SLOTS) {
      setError("At least two proposed slots are required.");
      return;
    }
    if (slots.some((slot) => !slot.date || !slot.startTime || !slot.endTime)) {
      setError("Complete all proposed slots.");
      return;
    }

    setSubmitting(true);
    try {
      await api.createInterviewInvitation(applicationId, {
        message: message.trim(),
        interviewer_employee_ids: selectedInterviewerIds,
        slots: slots.map((slot) => ({
          starts_at: toIsoFromDateAndTime(slot.date, slot.startTime),
          ends_at: toIsoFromDateAndTime(slot.date, slot.endTime),
        })),
      });
      setSuccess("Interview invitation created. The candidate has been notified.");
      setTimeout(() => router.push(`/hr/applications/${applicationId}`), 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create interview invitation");
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

  if (!application) {
    return <p className="text-red-700">{error || "Application not found"}</p>;
  }

  const selectedEmployees = employees.filter((employee) => selectedInterviewerIds.includes(employee.id));

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <Link href={`/hr/applications/${applicationId}`} className="text-sm text-gray-500 hover:text-gray-800">
          Application
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">Invite to interview</h1>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{error}</div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg text-sm">{success}</div>
      )}

      <ApplicationSection title="Candidate and job">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-xs text-gray-500">Candidate</p>
            <p className="mt-0.5 text-gray-900">{application.candidate.full_name}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Job</p>
            <p className="mt-0.5 text-gray-900">{application.job.title}</p>
          </div>
        </div>
      </ApplicationSection>

      <form onSubmit={handleSubmit} className="bg-white rounded-xl border shadow-sm p-6 space-y-6">
        <div>
          <label htmlFor="message" className="block text-sm font-medium text-gray-700 mb-1">
            Message from HR
          </label>
          <textarea
            id="message"
            required
            rows={4}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className={inputClass}
            placeholder="Tell the candidate what to expect..."
          />
        </div>

        <div>
          <p className="block text-sm font-medium text-gray-700 mb-2">Interviewers</p>
          {employees.length === 0 ? (
            <p className="text-sm text-gray-500">No active employees available.</p>
          ) : (
            <div className="max-h-56 overflow-y-auto border border-gray-200 rounded-lg divide-y">
              {employees.map((employee) => {
                const checked = selectedInterviewerIds.includes(employee.id);
                return (
                  <label
                    key={employee.id}
                    className="flex items-start gap-3 px-3 py-2.5 text-sm hover:bg-gray-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={checked}
                      onChange={() => toggleInterviewer(employee.id)}
                    />
                    <span>
                      <span className="block text-gray-900">
                        {employee.first_name} {employee.last_name}
                      </span>
                      <span className="block text-xs text-gray-500">{employee.position}</span>
                    </span>
                  </label>
                );
              })}
            </div>
          )}
          {selectedEmployees.length > 0 && (
            <p className="mt-2 text-xs text-gray-600">
              Selected: {selectedEmployees.map((e) => `${e.first_name} ${e.last_name}`).join(", ")}
            </p>
          )}
        </div>

        {slots.map((slot, index) => (
          <div key={index} className="space-y-3 border border-gray-200 rounded-lg p-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-medium text-gray-900">Proposed slot {index + 1}</h2>
              <button
                type="button"
                onClick={() => removeSlot(index)}
                disabled={slots.length <= MIN_SLOTS}
                className="text-sm text-gray-500 hover:text-red-600 disabled:opacity-40 disabled:hover:text-gray-500"
              >
                Remove
              </button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Date</label>
                <input
                  type="date"
                  required
                  value={slot.date}
                  onChange={(e) => updateSlot(index, "date", e.target.value)}
                  className={inputClass}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Start time</label>
                <input
                  type="time"
                  required
                  value={slot.startTime}
                  onChange={(e) => updateSlot(index, "startTime", e.target.value)}
                  className={inputClass}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">End time</label>
                <input
                  type="time"
                  required
                  value={slot.endTime}
                  onChange={(e) => updateSlot(index, "endTime", e.target.value)}
                  className={inputClass}
                />
              </div>
            </div>
          </div>
        ))}

        <button
          type="button"
          onClick={addSlot}
          disabled={slots.length >= MAX_SLOTS}
          className="w-full border border-dashed border-gray-300 text-gray-700 py-2.5 rounded-lg font-medium hover:bg-gray-50 disabled:opacity-50"
        >
          Add slot
        </button>

        <button
          type="submit"
          disabled={submitting || application.status !== "shortlisted"}
          className="w-full bg-brand-600 text-white py-2.5 rounded-lg font-medium hover:bg-brand-700 disabled:opacity-50"
        >
          {submitting ? "Creating invitation..." : "Create interview invitation"}
        </button>
      </form>
    </div>
  );
}

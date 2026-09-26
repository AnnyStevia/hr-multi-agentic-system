"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ApplicationSection } from "@/components/ApplicationSection";
import { api } from "@/lib/api";
import { hasActiveInterviewInvitation } from "@/lib/interviews";
import type { ApplicationDetail } from "@/types/applications";
import type { Employee } from "@/types/employees";

const inputClass =
  "w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition";

export default function InviteToInterviewPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const applicationId = Number(params.id);
  const [application, setApplication] = useState<ApplicationDetail | null>(null);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [primaryEmployeeId, setPrimaryEmployeeId] = useState<number | "">("");
  const [additionalIds, setAdditionalIds] = useState<number[]>([]);
  const [message, setMessage] = useState("");
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
            setError("An interview assignment is already in progress for this application.");
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

  const toggleAdditional = (employeeId: number) => {
    if (employeeId === primaryEmployeeId) return;
    setAdditionalIds((current) =>
      current.includes(employeeId)
        ? current.filter((id) => id !== employeeId)
        : [...current, employeeId],
    );
  };

  const handlePrimaryChange = (value: string) => {
    const next = value ? Number(value) : "";
    setPrimaryEmployeeId(next);
    if (typeof next === "number") {
      setAdditionalIds((current) => current.filter((id) => id !== next));
    }
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (!primaryEmployeeId) {
      setError("Select a primary interviewer.");
      return;
    }

    setSubmitting(true);
    try {
      await api.createInterviewInvitation(applicationId, {
        primary_employee_id: primaryEmployeeId,
        additional_employee_ids: additionalIds,
        message: message.trim() || null,
      });
      setSuccess("Interview panel assigned. The primary interviewer has been notified.");
      setTimeout(() => router.push(`/hr/applications/${applicationId}`), 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to assign interviewers");
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

  const additionalEmployees = employees.filter(
    (employee) => additionalIds.includes(employee.id) && employee.id !== primaryEmployeeId,
  );

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <Link href={`/hr/applications/${applicationId}`} className="text-sm text-gray-500 hover:text-gray-800">
          Application
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">Assign interview panel</h1>
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
          <label htmlFor="primary" className="block text-sm font-medium text-gray-700 mb-1">
            Primary interviewer
          </label>
          <select
            id="primary"
            required
            value={primaryEmployeeId}
            onChange={(e) => handlePrimaryChange(e.target.value)}
            className={inputClass}
          >
            <option value="">Select primary interviewer</option>
            {employees.map((employee) => (
              <option key={employee.id} value={employee.id}>
                {employee.first_name} {employee.last_name} — {employee.position}
              </option>
            ))}
          </select>
        </div>

        <div>
          <p className="block text-sm font-medium text-gray-700 mb-2">Additional interviewers</p>
          {employees.length === 0 ? (
            <p className="text-sm text-gray-500">No active employees available.</p>
          ) : (
            <div className="max-h-56 overflow-y-auto border border-gray-200 rounded-lg divide-y">
              {employees
                .filter((employee) => employee.id !== primaryEmployeeId)
                .map((employee) => {
                  const checked = additionalIds.includes(employee.id);
                  return (
                    <label
                      key={employee.id}
                      className="flex items-start gap-3 px-3 py-2.5 text-sm hover:bg-gray-50 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={checked}
                        onChange={() => toggleAdditional(employee.id)}
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
          {additionalEmployees.length > 0 && (
            <p className="mt-2 text-xs text-gray-600">
              Panel: {additionalEmployees.map((e) => `${e.first_name} ${e.last_name}`).join(", ")}
            </p>
          )}
        </div>

        <div>
          <label htmlFor="message" className="block text-sm font-medium text-gray-700 mb-1">
            Message to candidate (optional)
          </label>
          <textarea
            id="message"
            rows={3}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className={inputClass}
            placeholder="Shown when the candidate receives slot options..."
          />
        </div>

        <button
          type="submit"
          disabled={submitting || application.status !== "shortlisted"}
          className="w-full bg-brand-600 text-white py-2.5 rounded-lg font-medium hover:bg-brand-700 disabled:opacity-50"
        >
          {submitting ? "Assigning..." : "Assign interview panel"}
        </button>
      </form>
    </div>
  );
}

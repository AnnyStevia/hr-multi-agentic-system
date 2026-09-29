"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  EMPLOYEE_OFFBOARDING_REQUEST_REASONS,
  OFFBOARDING_REASON_LABELS,
  OFFBOARDING_REQUEST_STATUS_LABELS,
  type OffboardingRequestCreatePayload,
  type OffboardingRequestEmployeeView,
} from "@/types/offboarding";

const inputClass =
  "w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition";

function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

function statusClass(status: OffboardingRequestEmployeeView["status"]): string {
  switch (status) {
    case "pending":
      return "bg-amber-50 text-amber-800 border-amber-200";
    case "approved":
      return "bg-green-50 text-green-800 border-green-200";
    case "rejected":
      return "bg-red-50 text-red-800 border-red-200";
    default:
      return "bg-gray-50 text-gray-700 border-gray-200";
  }
}

export default function EmployeeOffboardingRequestPage() {
  const [requests, setRequests] = useState<OffboardingRequestEmployeeView[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [reason, setReason] =
    useState<OffboardingRequestCreatePayload["reason"]>("resignation");
  const [reasonDetails, setReasonDetails] = useState("");
  const [requestedLastWorkingDay, setRequestedLastWorkingDay] = useState("");

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      setRequests(await api.listMyOffboardingRequests());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load requests");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const pending = requests.find((item) => item.status === "pending");
  const latest = requests[0] ?? null;

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!requestedLastWorkingDay) {
      setError("Requested last working day is required");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await api.createMyOffboardingRequest({
        reason,
        reason_details: reasonDetails.trim() || null,
        requested_last_working_day: requestedLastWorkingDay,
      });
      setReason("resignation");
      setReasonDetails("");
      setRequestedLastWorkingDay("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit request");
    } finally {
      setSubmitting(false);
    }
  };

  const onCancel = async (requestId: number) => {
    setCancelling(true);
    setError("");
    try {
      await api.cancelMyOffboardingRequest(requestId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel request");
    } finally {
      setCancelling(false);
    }
  };

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <Link href="/employee/offboarding" className="text-sm text-brand-700 hover:underline">
          ← Back to offboarding
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">Request to leave</h1>
        <p className="mt-1 text-sm text-gray-600">
          Tell HR you want to leave. They will review your request before opening an
          offboarding case.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {latest && (
        <section className="bg-white rounded-xl border shadow-sm p-5 space-y-3">
          <h2 className="text-sm font-semibold text-gray-900">Your request</h2>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium ${statusClass(latest.status)}`}
            >
              {OFFBOARDING_REQUEST_STATUS_LABELS[latest.status]}
            </span>
            <span className="text-sm text-gray-700">
              {OFFBOARDING_REASON_LABELS[latest.reason]}
            </span>
          </div>
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-gray-500">Submitted</dt>
              <dd className="text-gray-900">{formatDate(latest.submitted_at)}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Requested last working day</dt>
              <dd className="text-gray-900">
                {formatDate(latest.requested_last_working_day)}
              </dd>
            </div>
            {latest.reviewed_at && (
              <div>
                <dt className="text-gray-500">HR decision date</dt>
                <dd className="text-gray-900">{formatDate(latest.reviewed_at)}</dd>
              </div>
            )}
          </dl>
          {latest.reason_details && (
            <p className="text-sm text-gray-600">{latest.reason_details}</p>
          )}
          {latest.rejection_reason && (
            <p className="text-sm text-red-700">HR note: {latest.rejection_reason}</p>
          )}
          {latest.status === "pending" && (
            <button
              type="button"
              disabled={cancelling}
              className="px-3 py-1.5 text-xs rounded-md border border-gray-300 hover:bg-gray-50 disabled:opacity-60"
              onClick={() => onCancel(latest.id)}
            >
              {cancelling ? "Cancelling…" : "Cancel request"}
            </button>
          )}
        </section>
      )}

      {!pending && (
        <form
          onSubmit={onSubmit}
          className="bg-white rounded-xl border shadow-sm p-5 space-y-4"
        >
          <h2 className="text-sm font-semibold text-gray-900">
            {latest ? "Submit a new request" : "New request"}
          </h2>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Reason</label>
            <select
              className={inputClass}
              value={reason}
              onChange={(e) =>
                setReason(e.target.value as OffboardingRequestCreatePayload["reason"])
              }
            >
              {EMPLOYEE_OFFBOARDING_REQUEST_REASONS.map((value) => (
                <option key={value} value={value}>
                  {OFFBOARDING_REASON_LABELS[value]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Requested last working day
            </label>
            <input
              type="date"
              className={inputClass}
              value={requestedLastWorkingDay}
              onChange={(e) => setRequestedLastWorkingDay(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Additional details (optional)
            </label>
            <textarea
              className={inputClass}
              rows={3}
              value={reasonDetails}
              onChange={(e) => setReasonDetails(e.target.value)}
              placeholder="Optional note for HR"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-2.5 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-60"
          >
            {submitting ? "Submitting…" : "Submit request"}
          </button>
        </form>
      )}
    </div>
  );
}

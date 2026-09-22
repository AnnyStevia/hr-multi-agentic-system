"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { BackLink } from "@/components/BackLink";
import { api } from "@/lib/api";
import {
  estimateLeaveDays,
  LEAVE_REQUEST_STATUS_LABELS,
  type LeaveBalance,
  type LeaveRequest,
  type LeaveType,
} from "@/types/leave";

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function datesOverlap(aStart: string, aEnd: string, bStart: string, bEnd: string): boolean {
  return aStart <= bEnd && aEnd >= bStart;
}

export default function EmployeeLeavePage() {
  const [balances, setBalances] = useState<LeaveBalance[]>([]);
  const [requests, setRequests] = useState<LeaveRequest[]>([]);
  const [types, setTypes] = useState<LeaveType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [leaveTypeId, setLeaveTypeId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [actingId, setActingId] = useState<number | null>(null);

  const estimatedDays = estimateLeaveDays(startDate, endDate);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const [balanceRows, requestRows, typeRows] = await Promise.all([
        api.listMyLeaveBalances(),
        api.listMyLeaveRequests(),
        api.listMyLeaveTypes(),
      ]);
      setBalances(balanceRows);
      setRequests(requestRows);
      setTypes(typeRows);
      setLeaveTypeId((current) => current || (typeRows[0] ? String(typeRows[0].id) : ""));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load leave data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    if (!leaveTypeId || !startDate || !endDate) {
      setError("Leave type and dates are required.");
      return;
    }
    if (endDate < startDate) {
      setError("End date must be on or after the start date.");
      return;
    }

    const balance = balances.find((row) => String(row.leave_type_id) === leaveTypeId);
    const days = estimateLeaveDays(startDate, endDate);
    if (balance && days != null && days > balance.days_available) {
      setError("This request exceeds your available leave balance for this type.");
      return;
    }

    const hasOverlap = requests.some(
      (request) =>
        (request.status === "pending" || request.status === "approved") &&
        datesOverlap(startDate, endDate, request.start_date, request.end_date)
    );
    if (hasOverlap) {
      setError(
        "You already have a pending or approved leave request that overlaps these dates. Choose different dates."
      );
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      await api.createMyLeaveRequest({
        leave_type_id: Number(leaveTypeId),
        start_date: startDate,
        end_date: endDate,
        reason: reason.trim() || null,
      });
      setStartDate("");
      setEndDate("");
      setReason("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create leave request");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = async (requestId: number) => {
    if (!window.confirm("Cancel this leave request?")) return;
    setActingId(requestId);
    setError("");
    try {
      await api.cancelMyLeaveRequest(requestId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel request");
    } finally {
      setActingId(null);
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
    <div className="space-y-6">
      <div>
        <BackLink href="/employee/dashboard" label="Dashboard" />
        <h1 className="mt-2 text-2xl font-bold text-brand-900">Leave</h1>
        <p className="mt-1 text-sm text-brand-300">
          View your allowances and submit leave requests. Days are calculated from your selected dates.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <section className="bg-white rounded-xl border border-brand-200 p-5 space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-brand-300">Leave balances</h2>
        {balances.length === 0 ? (
          <p className="text-sm text-brand-300">
            No leave policies are configured for the current year yet. Contact HR.
          </p>
        ) : (
          <ul className="divide-y divide-brand-100">
            {balances.map((balance) => (
              <li
                key={`${balance.leave_type_id}-${balance.year}`}
                className="py-2.5 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1"
              >
                <div className="min-w-0">
                  <span className="text-sm font-medium text-brand-900">{balance.leave_type_name}</span>
                  <span className="ml-2 text-xs text-brand-300">{balance.year}</span>
                </div>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-brand-300">
                  <span>
                    Allowed <strong className="text-brand-900 font-medium">{balance.days_allowed}</strong>
                  </span>
                  <span>
                    Used <strong className="text-brand-900 font-medium">{balance.days_used}</strong>
                  </span>
                  <span>
                    Pending <strong className="text-brand-900 font-medium">{balance.days_pending}</strong>
                  </span>
                  <span className="font-semibold text-brand-600">
                    Available {balance.days_available}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="bg-white rounded-xl border border-brand-200 p-5 space-y-4 max-w-xl">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-brand-300">Request leave</h2>
        {types.length === 0 ? (
          <p className="text-sm text-brand-300">No active leave types are available.</p>
        ) : (
          <form onSubmit={handleCreate} className="space-y-3">
            <div>
              <label className="block text-xs text-brand-300 mb-1" htmlFor="leave-type">
                Leave type
              </label>
              <select
                id="leave-type"
                value={leaveTypeId}
                onChange={(e) => setLeaveTypeId(e.target.value)}
                className="w-full border border-brand-200 rounded-lg px-3 py-2 text-sm text-brand-900 focus:outline-none focus:ring-2 focus:ring-brand-600/20"
              >
                {types.map((type) => (
                  <option key={type.id} value={type.id}>
                    {type.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-brand-300 mb-1" htmlFor="start-date">
                  Start date
                </label>
                <input
                  id="start-date"
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full border border-brand-200 rounded-lg px-3 py-2 text-sm text-brand-900 focus:outline-none focus:ring-2 focus:ring-brand-600/20"
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-brand-300 mb-1" htmlFor="end-date">
                  End date
                </label>
                <input
                  id="end-date"
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full border border-brand-200 rounded-lg px-3 py-2 text-sm text-brand-900 focus:outline-none focus:ring-2 focus:ring-brand-600/20"
                  required
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-brand-300 mb-1" htmlFor="reason">
                Reason (optional)
              </label>
              <textarea
                id="reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
                className="w-full border border-brand-200 rounded-lg px-3 py-2 text-sm text-brand-900 focus:outline-none focus:ring-2 focus:ring-brand-600/20"
              />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
              <p className="text-sm text-brand-300">
                {estimatedDays == null
                  ? "Select dates to see the calculated duration."
                  : `Calculated days: ${estimatedDays} (inclusive calendar days)`}
              </p>
              <button
                type="submit"
                disabled={submitting}
                className="bg-brand-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
              >
                {submitting ? "Submitting..." : "Submit request"}
              </button>
            </div>
          </form>
        )}
      </section>

      <section className="bg-white rounded-xl border border-brand-200 p-5 space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-brand-300">My leave requests</h2>
        {requests.length === 0 ? (
          <p className="text-sm text-brand-300">No leave requests yet.</p>
        ) : (
          <ul className="divide-y divide-brand-100">
            {requests.map((request) => (
              <li key={request.id} className="py-3 flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-brand-900">{request.leave_type_name}</p>
                  <p className="mt-0.5 text-sm text-brand-300">
                    {formatDate(request.start_date)} – {formatDate(request.end_date)} ·{" "}
                    {request.requested_days} day{request.requested_days === 1 ? "" : "s"}
                  </p>
                  {request.reason && (
                    <p className="mt-1 text-sm text-brand-300">{request.reason}</p>
                  )}
                  {request.status === "rejected" && request.rejection_reason && (
                    <p className="mt-1 text-sm text-red-700">
                      Rejected: {request.rejection_reason}
                    </p>
                  )}
                  <p className="mt-1 text-xs text-brand-300/80">
                    Created {formatDateTime(request.created_at)}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <span
                    className={`text-xs font-medium uppercase tracking-wide ${
                      request.status === "approved"
                        ? "text-brand-600"
                        : request.status === "rejected"
                          ? "text-red-600"
                          : "text-brand-300"
                    }`}
                  >
                    {LEAVE_REQUEST_STATUS_LABELS[request.status]}
                  </span>
                  {request.status === "pending" && (
                    <button
                      type="button"
                      disabled={actingId === request.id}
                      onClick={() => handleCancel(request.id)}
                      className="text-sm text-red-600 hover:text-red-700 disabled:opacity-50"
                    >
                      {actingId === request.id ? "Cancelling..." : "Cancel"}
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

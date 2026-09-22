"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  LEAVE_REQUEST_STATUS_LABELS,
  type LeaveRequest,
  type LeaveRequestStatus,
  type LeaveType,
} from "@/types/leave";

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

export default function HrLeaveRequestsPage() {
  const [requests, setRequests] = useState<LeaveRequest[]>([]);
  const [types, setTypes] = useState<LeaveType[]>([]);
  const [status, setStatus] = useState<LeaveRequestStatus | "">("pending");
  const [leaveTypeId, setLeaveTypeId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actingId, setActingId] = useState<number | null>(null);
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const [requestRows, typeRows] = await Promise.all([
        api.listLeaveRequests({
          status: status || undefined,
          leave_type_id: leaveTypeId ? Number(leaveTypeId) : undefined,
        }),
        api.listLeaveTypes(),
      ]);
      setRequests(requestRows);
      setTypes(typeRows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load leave requests");
    } finally {
      setLoading(false);
    }
  }, [status, leaveTypeId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleApprove = async (requestId: number) => {
    setActingId(requestId);
    setError("");
    try {
      await api.approveLeaveRequest(requestId);
      setRejectingId(null);
      setRejectionReason("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve request");
    } finally {
      setActingId(null);
    }
  };

  const startReject = (requestId: number) => {
    setRejectingId(requestId);
    setRejectionReason("");
    setError("");
  };

  const cancelReject = () => {
    setRejectingId(null);
    setRejectionReason("");
  };

  const handleReject = async (event: FormEvent, requestId: number) => {
    event.preventDefault();
    const reason = rejectionReason.trim();
    if (!reason) {
      setError("A rejection reason is required.");
      return;
    }
    setActingId(requestId);
    setError("");
    try {
      await api.rejectLeaveRequest(requestId, reason);
      setRejectingId(null);
      setRejectionReason("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reject request");
    } finally {
      setActingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-brand-900">Leave requests</h1>
          <p className="mt-1 text-sm text-brand-300">Review and approve employee leave requests.</p>
        </div>
        <div className="flex flex-wrap gap-2 text-sm">
          <Link href="/hr/leave/types" className="text-brand-600 hover:text-brand-700">
            Leave types
          </Link>
          <span className="text-brand-100">·</span>
          <Link href="/hr/leave/policies" className="text-brand-600 hover:text-brand-700">
            Policies
          </Link>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="bg-white rounded-xl border border-brand-200 p-4 flex flex-wrap gap-3">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as LeaveRequestStatus | "")}
          className="border border-brand-100 rounded-lg px-3 py-2 text-sm text-brand-900"
        >
          <option value="">All statuses</option>
          {Object.entries(LEAVE_REQUEST_STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select
          value={leaveTypeId}
          onChange={(e) => setLeaveTypeId(e.target.value)}
          className="border border-brand-100 rounded-lg px-3 py-2 text-sm text-brand-900"
        >
          <option value="">All types</option>
          {types.map((type) => (
            <option key={type.id} value={type.id}>
              {type.name}
            </option>
          ))}
        </select>
      </div>

      <div className="bg-white rounded-xl border border-brand-200 overflow-hidden">
        {loading ? (
          <div className="py-16 flex justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
          </div>
        ) : requests.length === 0 ? (
          <p className="py-16 text-center text-sm text-brand-300">No leave requests found.</p>
        ) : (
          <ul className="divide-y divide-brand-100">
            {requests.map((request) => (
              <li key={request.id} className="p-4 space-y-3">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-brand-900">
                      {request.employee_name || `Employee #${request.employee_id}`}
                    </p>
                    <p className="mt-1 text-sm text-brand-300">
                      {request.leave_type_name} · {formatDate(request.start_date)} –{" "}
                      {formatDate(request.end_date)} · {request.requested_days} day
                      {request.requested_days === 1 ? "" : "s"}
                    </p>
                    {request.reason && (
                      <p className="mt-1 text-sm text-brand-300">{request.reason}</p>
                    )}
                    {request.status === "rejected" && request.rejection_reason && (
                      <p className="mt-1 text-sm text-red-700">
                        Rejected: {request.rejection_reason}
                      </p>
                    )}
                    <p className="mt-1 text-xs text-brand-300">
                      {LEAVE_REQUEST_STATUS_LABELS[request.status]}
                    </p>
                  </div>
                  {request.status === "pending" && rejectingId !== request.id && (
                    <div className="flex gap-2">
                      <button
                        type="button"
                        disabled={actingId === request.id}
                        onClick={() => handleApprove(request.id)}
                        className="bg-brand-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-brand-700 disabled:opacity-50"
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        disabled={actingId === request.id}
                        onClick={() => startReject(request.id)}
                        className="border border-red-200 text-red-700 px-3 py-1.5 rounded-lg text-sm hover:bg-red-50 disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </div>
                  )}
                </div>
                {request.status === "pending" && rejectingId === request.id && (
                  <form
                    onSubmit={(e) => void handleReject(e, request.id)}
                    className="max-w-md space-y-2 rounded-lg border border-brand-200 bg-brand-100 p-3"
                  >
                    <label
                      className="block text-xs font-medium text-brand-900"
                      htmlFor={`reject-reason-${request.id}`}
                    >
                      Rejection reason
                    </label>
                    <textarea
                      id={`reject-reason-${request.id}`}
                      value={rejectionReason}
                      onChange={(e) => setRejectionReason(e.target.value)}
                      rows={2}
                      required
                      placeholder="Explain why this request is rejected"
                      className="w-full border border-brand-100 rounded-lg px-3 py-2 text-sm text-brand-900 focus:outline-none focus:ring-2 focus:ring-brand-600/30"
                      autoFocus
                    />
                    <div className="flex gap-2">
                      <button
                        type="submit"
                        disabled={actingId === request.id}
                        className="bg-red-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-red-700 disabled:opacity-50"
                      >
                        {actingId === request.id ? "Rejecting..." : "Confirm reject"}
                      </button>
                      <button
                        type="button"
                        onClick={cancelReject}
                        className="border border-brand-100 text-brand-900 px-3 py-1.5 rounded-lg text-sm hover:bg-white"
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

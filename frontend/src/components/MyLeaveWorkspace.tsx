"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { BackLink } from "@/components/BackLink";
import { LeaveApprovalStages } from "@/components/LeaveApprovalStages";
import {
  MonthCalendar,
  type DayVisualState,
} from "@/components/calendar/MonthCalendar";
import { formatDisplayDate } from "@/components/calendar/dateUtils";
import { api } from "@/lib/api";
import {
  eachDateInRange,
  estimateLeaveDays,
  LEAVE_CANCELLATION_STATUS_LABELS,
  LEAVE_REQUEST_STATUS_LABELS,
  type LeaveBalance,
  type LeaveCalendarPeriod,
  type LeaveRequest,
  type LeaveType,
} from "@/types/leave";

export type MyLeaveWorkspaceProps = {
  backHref: string;
  backLabel: string;
  title?: string;
  showTeamRequests?: boolean;
};

function formatDate(value: string): string {
  return formatDisplayDate(value);
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function datesOverlap(aStart: string, aEnd: string, bStart: string, bEnd: string): boolean {
  return aStart <= bEnd && aEnd >= bStart;
}

function buildDayStates(periods: LeaveCalendarPeriod[]): {
  dayStates: Record<string, DayVisualState>;
  disabled: Set<string>;
} {
  const dayStates: Record<string, DayVisualState> = {};
  const disabled = new Set<string>();
  for (const period of periods) {
    for (const iso of eachDateInRange(period.start_date, period.end_date)) {
      disabled.add(iso);
      if (period.status === "approved") dayStates[iso] = "approved";
      else if (period.status === "pending" && dayStates[iso] !== "approved") {
        dayStates[iso] = "pending";
      }
      if (dayStates[iso] === "approved" || dayStates[iso] === "pending") {
        // already set visual; unavailable selection blocked via disabled
      }
    }
  }
  return { dayStates, disabled };
}

export function MyLeaveWorkspace({
  backHref,
  backLabel,
  title = "Leave",
  showTeamRequests = false,
}: MyLeaveWorkspaceProps) {
  const now = new Date();
  const [balances, setBalances] = useState<LeaveBalance[]>([]);
  const [requests, setRequests] = useState<LeaveRequest[]>([]);
  const [teamRequests, setTeamRequests] = useState<LeaveRequest[]>([]);
  const [types, setTypes] = useState<LeaveType[]>([]);
  const [periods, setPeriods] = useState<LeaveCalendarPeriod[]>([]);
  const [viewYear, setViewYear] = useState(now.getFullYear());
  const [viewMonth, setViewMonth] = useState(now.getMonth() + 1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [leaveTypeId, setLeaveTypeId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [actingId, setActingId] = useState<number | null>(null);
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const [cancellingId, setCancellingId] = useState<number | null>(null);
  const [cancellationReason, setCancellationReason] = useState("");
  const [rejectingCancellationId, setRejectingCancellationId] = useState<number | null>(null);
  const [cancellationRejectReason, setCancellationRejectReason] = useState("");

  const todayIso = useMemo(() => {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }, []);

  const estimatedDays = estimateLeaveDays(startDate, endDate);
  const { dayStates, disabled } = useMemo(() => buildDayStates(periods), [periods]);

  const selectedBalance = balances.find((row) => String(row.leave_type_id) === leaveTypeId);
  const selectedType = types.find((row) => String(row.id) === leaveTypeId);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const [balanceRows, requestRows, typeRows, calendar, pendingTeam, cancelTeam] =
        await Promise.all([
          api.listMyLeaveBalances(),
          api.listMyLeaveRequests(),
          api.listMyLeaveTypes(),
          api.getMyLeaveCalendar(viewYear, viewMonth),
          showTeamRequests
            ? api.listMyTeamLeaveRequests("pending").catch(() => [] as LeaveRequest[])
            : Promise.resolve([] as LeaveRequest[]),
          showTeamRequests
            ? api
                .listMyTeamLeaveRequests("approved", "requested")
                .catch(() => [] as LeaveRequest[])
            : Promise.resolve([] as LeaveRequest[]),
        ]);
      setBalances(balanceRows);
      setRequests(requestRows);
      setTypes(typeRows);
      setPeriods(calendar.periods);
      const seen = new Set<number>();
      const mergedTeam: LeaveRequest[] = [];
      for (const row of [...pendingTeam, ...cancelTeam]) {
        if (seen.has(row.id)) continue;
        seen.add(row.id);
        mergedTeam.push(row);
      }
      setTeamRequests(mergedTeam);
      setLeaveTypeId((current) => current || (typeRows[0] ? String(typeRows[0].id) : ""));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load leave data");
    } finally {
      setLoading(false);
    }
  }, [viewYear, viewMonth, showTeamRequests]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleSelectDate = (iso: string) => {
    if (disabled.has(iso)) {
      setError("That date is unavailable because of an existing pending or approved leave request.");
      return;
    }
    setError("");
    if (!startDate || (startDate && endDate)) {
      setStartDate(iso);
      setEndDate("");
      return;
    }
    if (iso < startDate) {
      setStartDate(iso);
      setEndDate("");
      return;
    }
    // ensure no unavailable days inside range
    for (const day of eachDateInRange(startDate, iso)) {
      if (disabled.has(day)) {
        setError(
          "You already have a pending or approved leave request that overlaps these dates. Choose different dates."
        );
        return;
      }
    }
    setEndDate(iso);
  };

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    if (!leaveTypeId || !startDate || !endDate) {
      setError("Leave type and a date range are required.");
      return;
    }
    if (endDate < startDate) {
      setError("End date must be on or after the start date.");
      return;
    }
    const days = estimateLeaveDays(startDate, endDate);
    if (selectedBalance && days != null && days > selectedBalance.days_available) {
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

  const handleRequestCancellation = async (event: FormEvent, requestId: number) => {
    event.preventDefault();
    const reasonText = cancellationReason.trim();
    if (!reasonText) {
      setError("A cancellation reason is required.");
      return;
    }
    setActingId(requestId);
    setError("");
    try {
      await api.requestMyLeaveCancellation(requestId, reasonText);
      setCancellingId(null);
      setCancellationReason("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to request cancellation");
    } finally {
      setActingId(null);
    }
  };

  const handleApproveTeam = async (requestId: number) => {
    setActingId(requestId);
    setError("");
    try {
      await api.approveLeaveRequest(requestId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve request");
    } finally {
      setActingId(null);
    }
  };

  const handleRejectTeam = async (event: FormEvent, requestId: number) => {
    event.preventDefault();
    const reasonText = rejectionReason.trim();
    if (!reasonText) {
      setError("A rejection reason is required.");
      return;
    }
    setActingId(requestId);
    setError("");
    try {
      await api.rejectLeaveRequest(requestId, reasonText);
      setRejectingId(null);
      setRejectionReason("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reject request");
    } finally {
      setActingId(null);
    }
  };

  const handleApproveCancellation = async (requestId: number) => {
    setActingId(requestId);
    setError("");
    try {
      await api.approveLeaveCancellation(requestId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve cancellation");
    } finally {
      setActingId(null);
    }
  };

  const handleRejectCancellation = async (event: FormEvent, requestId: number) => {
    event.preventDefault();
    const reasonText = cancellationRejectReason.trim();
    if (!reasonText) {
      setError("A rejection reason is required.");
      return;
    }
    setActingId(requestId);
    setError("");
    try {
      await api.rejectLeaveCancellation(requestId, reasonText);
      setRejectingCancellationId(null);
      setCancellationRejectReason("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reject cancellation");
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
        <BackLink href={backHref} label={backLabel} />
        <h1 className="mt-2 text-2xl font-bold text-brand-900">{title}</h1>
        <p className="mt-1 text-sm text-brand-300">
          Select dates on the calendar to request leave. The server validates days and balance.
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

      <section className="bg-white rounded-xl border border-brand-200 p-5 space-y-4">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-brand-300">Leave calendar</h2>
        <MonthCalendar
          year={viewYear}
          month={viewMonth}
          onMonthChange={(y, m) => {
            setViewYear(y);
            setViewMonth(m);
          }}
          selectedStart={startDate || null}
          selectedEnd={endDate || null}
          onSelectDate={handleSelectDate}
          dayStates={dayStates}
          disabledDates={disabled}
          className="max-w-xl border-0 p-0"
        />
        <ul className="flex flex-wrap gap-4 text-xs text-brand-300">
          <li className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-brand-100 border border-brand-200" /> Available
          </li>
          <li className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-brand-600/20" /> Approved
          </li>
          <li className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-amber-100" /> Pending
          </li>
          <li className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-brand-100 opacity-50" /> Unavailable
          </li>
          <li className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm ring-1 ring-brand-600" /> Today
          </li>
          <li className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-brand-600" /> Selected
          </li>
        </ul>
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

            <div className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-3 text-sm space-y-1">
              <p className="text-brand-900">
                <span className="text-brand-300">Start:</span>{" "}
                {startDate ? formatDate(startDate) : "—"}
              </p>
              <p className="text-brand-900">
                <span className="text-brand-300">End:</span> {endDate ? formatDate(endDate) : "—"}
              </p>
              <p className="text-brand-900">
                <span className="text-brand-300">Days:</span>{" "}
                {estimatedDays != null ? estimatedDays : "—"}
              </p>
              <p className="text-brand-900">
                <span className="text-brand-300">Type:</span> {selectedType?.name ?? "—"}
              </p>
              <p className="text-brand-900">
                <span className="text-brand-300">Available balance:</span>{" "}
                {selectedBalance != null ? selectedBalance.days_available : "—"}
              </p>
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
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setStartDate("");
                  setEndDate("");
                }}
                className="border border-brand-200 text-brand-900 px-4 py-2 rounded-lg text-sm hover:bg-brand-100"
              >
                Clear dates
              </button>
              <button
                type="submit"
                disabled={submitting || !startDate || !endDate}
                className="bg-brand-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
              >
                {submitting ? "Submitting..." : "Submit request"}
              </button>
            </div>
          </form>
        )}
      </section>

      {showTeamRequests && teamRequests.length > 0 && (
        <section className="bg-white rounded-xl border border-brand-200 p-5 space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-brand-300">
            Team leave requests
          </h2>
          <ul className="divide-y divide-brand-100">
            {teamRequests.map((request) => {
              const isCancellation = request.cancellation_status === "requested";
              return (
              <li key={request.id} className="py-3 space-y-2">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-brand-900">
                      {request.employee_name || `Employee #${request.employee_id}`}
                    </p>
                    <p className="mt-0.5 text-sm text-brand-300">
                      {request.leave_type_name} · {formatDate(request.start_date)} –{" "}
                      {formatDate(request.end_date)} · {request.requested_days} day
                      {request.requested_days === 1 ? "" : "s"}
                    </p>
                    {isCancellation && (
                      <p className="mt-1 text-xs font-medium text-amber-700">
                        Cancellation requested
                        {request.cancellation_reason
                          ? `: ${request.cancellation_reason}`
                          : ""}
                      </p>
                    )}
                    {!isCancellation && <LeaveApprovalStages request={request} />}
                  </div>
                  {rejectingId !== request.id &&
                    rejectingCancellationId !== request.id && (
                    <div className="flex gap-2">
                      {isCancellation ? (
                        <>
                          <button
                            type="button"
                            disabled={actingId === request.id}
                            onClick={() => handleApproveCancellation(request.id)}
                            className="bg-brand-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-brand-700 disabled:opacity-50"
                          >
                            Approve cancellation
                          </button>
                          <button
                            type="button"
                            disabled={actingId === request.id}
                            onClick={() => {
                              setRejectingCancellationId(request.id);
                              setCancellationRejectReason("");
                            }}
                            className="border border-red-200 text-red-700 px-3 py-1.5 rounded-lg text-sm hover:bg-red-50 disabled:opacity-50"
                          >
                            Reject cancellation
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            disabled={actingId === request.id}
                            onClick={() => handleApproveTeam(request.id)}
                            className="bg-brand-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-brand-700 disabled:opacity-50"
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            disabled={actingId === request.id}
                            onClick={() => {
                              setRejectingId(request.id);
                              setRejectionReason("");
                            }}
                            className="border border-red-200 text-red-700 px-3 py-1.5 rounded-lg text-sm hover:bg-red-50 disabled:opacity-50"
                          >
                            Reject
                          </button>
                        </>
                      )}
                    </div>
                  )}
                </div>
                {rejectingId === request.id && (
                  <form
                    onSubmit={(e) => void handleRejectTeam(e, request.id)}
                    className="max-w-md space-y-2 rounded-lg border border-brand-200 bg-brand-100 p-3"
                  >
                    <textarea
                      value={rejectionReason}
                      onChange={(e) => setRejectionReason(e.target.value)}
                      rows={2}
                      required
                      placeholder="Rejection reason"
                      className="w-full border border-brand-200 rounded-lg px-3 py-2 text-sm"
                    />
                    <div className="flex gap-2">
                      <button
                        type="submit"
                        disabled={actingId === request.id}
                        className="bg-red-600 text-white px-3 py-1.5 rounded-lg text-sm"
                      >
                        Confirm reject
                      </button>
                      <button
                        type="button"
                        onClick={() => setRejectingId(null)}
                        className="border border-brand-200 px-3 py-1.5 rounded-lg text-sm"
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                )}
                {rejectingCancellationId === request.id && (
                  <form
                    onSubmit={(e) => void handleRejectCancellation(e, request.id)}
                    className="max-w-md space-y-2 rounded-lg border border-brand-200 bg-brand-100 p-3"
                  >
                    <textarea
                      value={cancellationRejectReason}
                      onChange={(e) => setCancellationRejectReason(e.target.value)}
                      rows={2}
                      required
                      placeholder="Why reject this cancellation?"
                      className="w-full border border-brand-200 rounded-lg px-3 py-2 text-sm"
                    />
                    <div className="flex gap-2">
                      <button
                        type="submit"
                        disabled={actingId === request.id}
                        className="bg-red-600 text-white px-3 py-1.5 rounded-lg text-sm"
                      >
                        Confirm reject
                      </button>
                      <button
                        type="button"
                        onClick={() => setRejectingCancellationId(null)}
                        className="border border-brand-200 px-3 py-1.5 rounded-lg text-sm"
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                )}
              </li>
              );
            })}
          </ul>
        </section>
      )}

      <section className="bg-white rounded-xl border border-brand-200 p-5 space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-brand-300">My leave requests</h2>
        {requests.length === 0 ? (
          <p className="text-sm text-brand-300">No leave requests yet.</p>
        ) : (
          <ul className="divide-y divide-brand-100">
            {requests.map((request) => {
              const canRequestCancel =
                request.status === "approved" &&
                request.start_date > todayIso &&
                request.cancellation_status !== "requested";
              return (
              <li key={request.id} className="py-3 space-y-2">
                <div className="flex flex-wrap items-start justify-between gap-3">
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
                  {request.cancellation_status === "requested" && (
                    <p className="mt-1 text-xs font-medium text-amber-700">
                      {LEAVE_CANCELLATION_STATUS_LABELS.requested}
                    </p>
                  )}
                  {request.cancellation_status === "rejected" && (
                    <p className="mt-1 text-sm text-red-700">
                      Cancellation rejected
                      {request.cancellation_rejection_reason
                        ? `: ${request.cancellation_rejection_reason}`
                        : ""}
                    </p>
                  )}
                  <LeaveApprovalStages request={request} />
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
                  {canRequestCancel && cancellingId !== request.id && (
                    <button
                      type="button"
                      disabled={actingId === request.id}
                      onClick={() => {
                        setCancellingId(request.id);
                        setCancellationReason("");
                      }}
                      className="text-sm text-amber-700 hover:text-amber-800 disabled:opacity-50"
                    >
                      Request cancellation
                    </button>
                  )}
                </div>
                </div>
                {cancellingId === request.id && (
                  <form
                    onSubmit={(e) => void handleRequestCancellation(e, request.id)}
                    className="max-w-md space-y-2 rounded-lg border border-brand-200 bg-brand-100 p-3"
                  >
                    <textarea
                      value={cancellationReason}
                      onChange={(e) => setCancellationReason(e.target.value)}
                      rows={2}
                      required
                      placeholder="Why cancel this approved leave?"
                      className="w-full border border-brand-200 rounded-lg px-3 py-2 text-sm"
                    />
                    <div className="flex gap-2">
                      <button
                        type="submit"
                        disabled={actingId === request.id}
                        className="bg-amber-600 text-white px-3 py-1.5 rounded-lg text-sm disabled:opacity-50"
                      >
                        Submit cancellation request
                      </button>
                      <button
                        type="button"
                        onClick={() => setCancellingId(null)}
                        className="border border-brand-200 px-3 py-1.5 rounded-lg text-sm"
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                )}
              </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

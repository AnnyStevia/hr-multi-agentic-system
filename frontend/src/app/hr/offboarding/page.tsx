"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { OffboardingStatusBadge } from "@/components/OffboardingStatusBadge";
import { api } from "@/lib/api";
import type { Employee } from "@/types/employees";
import {
  OFFBOARDING_REASON_LABELS,
  type OffboardingCreatePayload,
  type OffboardingListItem,
  type OffboardingReason,
  type OffboardingStatus,
} from "@/types/offboarding";

const inputClass =
  "w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition";

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

const REASONS = Object.keys(OFFBOARDING_REASON_LABELS) as OffboardingReason[];

export default function OffboardingListPage() {
  const [items, setItems] = useState<OffboardingListItem[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [statusFilter, setStatusFilter] = useState<OffboardingStatus | "">("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [employeeId, setEmployeeId] = useState("");
  const [reason, setReason] = useState<OffboardingReason>("resignation");
  const [reasonDetails, setReasonDetails] = useState("");
  const [lastWorkingDay, setLastWorkingDay] = useState("");

  const load = async (status?: OffboardingStatus | "") => {
    setError("");
    setLoading(true);
    try {
      const filter = status === undefined ? statusFilter : status;
      const [list, employeeList] = await Promise.all([
        api.listOffboardings(filter ? { status: filter } : undefined),
        api.listEmployees({ status: "active" }),
      ]);
      setItems(list);
      setEmployees(employeeList.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load offboarding cases");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onCreate = async (event: FormEvent) => {
    event.preventDefault();
    if (!employeeId || !lastWorkingDay) {
      setError("Employee and last working day are required");
      return;
    }
    setCreating(true);
    setError("");
    try {
      const payload: OffboardingCreatePayload = {
        employee_id: Number(employeeId),
        reason,
        last_working_day: lastWorkingDay,
      };
      if (reasonDetails.trim()) {
        payload.reason_details = reasonDetails.trim();
      }
      await api.createOffboarding(payload);
      setEmployeeId("");
      setReason("resignation");
      setReasonDetails("");
      setLastWorkingDay("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create offboarding case");
    } finally {
      setCreating(false);
    }
  };

  if (loading && items.length === 0) {
    return (
      <div className="py-16 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Offboarding</h1>
        <p className="mt-1 text-sm text-gray-600">
          Manage employee offboarding cases. Checklist and clearance come in later phases.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <form
        onSubmit={onCreate}
        className="bg-white rounded-xl border shadow-sm p-5 grid gap-4 md:grid-cols-2"
      >
        <h2 className="md:col-span-2 text-sm font-semibold text-gray-900">Create case</h2>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Employee</label>
          <select
            className={inputClass}
            value={employeeId}
            onChange={(e) => setEmployeeId(e.target.value)}
            required
          >
            <option value="">Select active employee…</option>
            {employees.map((emp) => (
              <option key={emp.id} value={emp.id}>
                {emp.first_name} {emp.last_name} — {emp.position}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Reason</label>
          <select
            className={inputClass}
            value={reason}
            onChange={(e) => setReason(e.target.value as OffboardingReason)}
          >
            {REASONS.map((value) => (
              <option key={value} value={value}>
                {OFFBOARDING_REASON_LABELS[value]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Last working day</label>
          <input
            type="date"
            className={inputClass}
            value={lastWorkingDay}
            onChange={(e) => setLastWorkingDay(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Reason details</label>
          <input
            className={inputClass}
            value={reasonDetails}
            onChange={(e) => setReasonDetails(e.target.value)}
            placeholder="Optional"
          />
        </div>
        <div className="md:col-span-2">
          <button
            type="submit"
            disabled={creating}
            className="px-4 py-2.5 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-60"
          >
            {creating ? "Creating…" : "Create offboarding"}
          </button>
        </div>
      </form>

      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-600">Filter status</label>
        <select
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
          value={statusFilter}
          onChange={(e) => {
            const value = e.target.value as OffboardingStatus | "";
            setStatusFilter(value);
            load(value);
          }}
        >
          <option value="">All</option>
          {(
            [
              "initiated",
              "in_progress",
              "pending_clearance",
              "completed",
              "cancelled",
            ] as OffboardingStatus[]
          ).map((status) => (
            <option key={status} value={status}>
              {status.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      </div>

      {items.length === 0 ? (
        <div className="bg-white rounded-xl border shadow-sm p-10 text-center">
          <p className="text-sm text-gray-600">No offboarding cases yet.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Employee
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Reason
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Last working day
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Initiated
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {items.map((item) => (
                  <tr key={item.id}>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <div className="font-medium">{item.employee_name}</div>
                      <div className="text-xs text-gray-500">{item.position}</div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {OFFBOARDING_REASON_LABELS[item.reason]}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {formatDate(item.last_working_day)}
                    </td>
                    <td className="px-4 py-3">
                      <OffboardingStatusBadge status={item.status} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {formatDate(item.initiated_at)}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <Link
                        href={`/hr/offboarding/${item.id}`}
                        className="text-brand-700 font-medium hover:underline"
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

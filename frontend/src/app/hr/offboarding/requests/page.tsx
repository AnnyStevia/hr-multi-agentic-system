"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  OFFBOARDING_REASON_LABELS,
  OFFBOARDING_REQUEST_STATUS_LABELS,
  type OffboardingRequestListItem,
  type OffboardingRequestStatus,
} from "@/types/offboarding";

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

export default function HrOffboardingRequestsPage() {
  const router = useRouter();
  const [items, setItems] = useState<OffboardingRequestListItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<OffboardingRequestStatus | "">("pending");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<number | null>(null);

  const load = useCallback(async (status?: OffboardingRequestStatus | "") => {
    setError("");
    setLoading(true);
    try {
      const filter = status === undefined ? statusFilter : status;
      const list = await api.listOffboardingRequests(
        filter ? { status: filter } : undefined,
      );
      setItems(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load requests");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const approve = async (id: number) => {
    setActingId(id);
    setError("");
    try {
      const caseDetail = await api.approveOffboardingRequest(id);
      router.push(`/hr/offboarding/${caseDetail.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve");
      setActingId(null);
    }
  };

  const reject = async (id: number) => {
    const reasonText = window.prompt("Optional rejection reason") ?? "";
    setActingId(id);
    setError("");
    try {
      await api.rejectOffboardingRequest(id, reasonText || null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reject");
    } finally {
      setActingId(null);
    }
  };

  const createCase = async (id: number) => {
    setActingId(id);
    setError("");
    try {
      const caseDetail = await api.createOffboardingCaseFromRequest(id);
      router.push(`/hr/offboarding/${caseDetail.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create case");
      setActingId(null);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <Link href="/hr/offboarding" className="text-sm text-brand-700 hover:underline">
          ← Back to offboarding cases
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">Offboarding requests</h1>
        <p className="mt-1 text-sm text-gray-600">
          Approve a request to open the offboarding case and checklist. You will be taken to
          the case page. Reject leaves the request closed with no case.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-600">Filter status</label>
        <select
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
          value={statusFilter}
          onChange={(e) => {
            const value = e.target.value as OffboardingRequestStatus | "";
            setStatusFilter(value);
            load(value);
          }}
        >
          <option value="">All</option>
          {(
            ["pending", "approved", "rejected", "cancelled"] as OffboardingRequestStatus[]
          ).map((status) => (
            <option key={status} value={status}>
              {OFFBOARDING_REQUEST_STATUS_LABELS[status]}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="py-16 flex justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
        </div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-xl border shadow-sm p-10 text-center">
          <p className="text-sm text-gray-600">No offboarding requests.</p>
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
                    Requested last day
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Submitted
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {items.map((item) => (
                  <tr key={item.id} id={`request-${item.id}`}>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <div className="font-medium">{item.employee_name}</div>
                      <div className="text-xs text-gray-500">{item.position}</div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {OFFBOARDING_REASON_LABELS[item.reason]}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {formatDate(item.requested_last_working_day)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {OFFBOARDING_REQUEST_STATUS_LABELS[item.status]}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {formatDate(item.submitted_at)}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      {item.status === "pending" ? (
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            disabled={actingId !== null}
                            className="text-brand-700 font-medium hover:underline disabled:opacity-60"
                            onClick={() => approve(item.id)}
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            disabled={actingId !== null}
                            className="text-red-700 font-medium hover:underline disabled:opacity-60"
                            onClick={() => reject(item.id)}
                          >
                            Reject
                          </button>
                        </div>
                      ) : item.status === "approved" && item.offboarding_case_id == null ? (
                        <button
                          type="button"
                          disabled={actingId !== null}
                          className="text-brand-700 font-medium hover:underline disabled:opacity-60"
                          onClick={() => createCase(item.id)}
                        >
                          {actingId === item.id ? "Creating…" : "Create Offboarding Case"}
                        </button>
                      ) : item.offboarding_case_id != null ? (
                        <Link
                          href={`/hr/offboarding/${item.offboarding_case_id}`}
                          className="text-brand-700 font-medium hover:underline"
                        >
                          View case
                        </Link>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
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

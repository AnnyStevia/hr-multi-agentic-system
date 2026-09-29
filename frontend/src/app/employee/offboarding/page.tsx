"use client";

import { useEffect, useState } from "react";
import { OffboardingStatusBadge } from "@/components/OffboardingStatusBadge";
import { api } from "@/lib/api";
import {
  OFFBOARDING_REASON_LABELS,
  type OffboardingEmployeeView,
} from "@/types/offboarding";

function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

export default function EmployeeOffboardingPage() {
  const [items, setItems] = useState<OffboardingEmployeeView[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setError("");
      setLoading(true);
      try {
        setItems(await api.listMyOffboardings());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load offboarding");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

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
        <h1 className="text-2xl font-bold text-gray-900">My offboarding</h1>
        <p className="mt-1 text-sm text-gray-600">
          View your offboarding case status. Only HR can change the case.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {items.length === 0 ? (
        <div className="bg-white rounded-xl border shadow-sm p-10 text-center">
          <p className="text-sm text-gray-600">You have no offboarding cases.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((item) => (
            <div key={item.id} className="bg-white rounded-xl border shadow-sm p-5 space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <OffboardingStatusBadge status={item.status} />
                <span className="text-sm text-gray-700">
                  {OFFBOARDING_REASON_LABELS[item.reason]}
                </span>
              </div>
              <dl className="grid gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-gray-500">Last working day</dt>
                  <dd className="text-gray-900">{formatDate(item.last_working_day)}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">Initiated</dt>
                  <dd className="text-gray-900">{formatDate(item.initiated_at)}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">Completed</dt>
                  <dd className="text-gray-900">{formatDate(item.completed_at)}</dd>
                </div>
              </dl>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

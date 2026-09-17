"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { OnboardingStatusBadge } from "@/components/OnboardingStatusBadge";
import { api } from "@/lib/api";
import type { OnboardingListItem } from "@/types/onboarding";

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

export default function OnboardingListPage() {
  const [items, setItems] = useState<OnboardingListItem[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setError("");
      setLoading(true);
      try {
        setItems(await api.listOnboardings());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load onboarding records");
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
    <div className="max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Onboarding</h1>
        <p className="mt-1 text-sm text-gray-600">
          {items.length} employee{items.length === 1 ? "" : "s"} with an onboarding record.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm mb-4">
          {error}
        </div>
      )}

      {items.length === 0 ? (
        <div className="bg-white rounded-xl border shadow-sm p-10 text-center">
          <p className="text-sm text-gray-600">No onboarding records yet.</p>
          <p className="mt-1 text-xs text-gray-500">
            Onboarding records are created automatically when a candidate is hired.
          </p>
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
                    Position
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Started
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                    Tasks
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm">
                      <Link
                        href={`/hr/onboarding/${item.id}`}
                        className="font-medium text-brand-700 hover:text-brand-800"
                      >
                        {item.employee_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">{item.position}</td>
                    <td className="px-4 py-3 text-sm">
                      <OnboardingStatusBadge status={item.status} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">{formatDate(item.started_at)}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {item.completed_tasks_count}/{item.total_tasks_count}
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

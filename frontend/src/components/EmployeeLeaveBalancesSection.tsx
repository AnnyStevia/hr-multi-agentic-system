"use client";

import { useEffect, useState } from "react";
import { ApplicationSection } from "@/components/ApplicationSection";
import { api } from "@/lib/api";
import type { LeaveBalance } from "@/types/leave";

export function EmployeeLeaveBalancesSection({ employeeId }: { employeeId: number }) {
  const [balances, setBalances] = useState<LeaveBalance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        setBalances(await api.listEmployeeLeaveBalances(employeeId));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load leave balances");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [employeeId]);

  return (
    <ApplicationSection title="Leave balances">
      {error && (
        <div className="mb-3 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-lg text-sm">
          {error}
        </div>
      )}
      {loading ? (
        <div className="py-6 flex justify-center">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-brand-600" />
        </div>
      ) : balances.length === 0 ? (
        <p className="text-sm text-gray-500">No leave policies for the current year.</p>
      ) : (
        <ul className="divide-y divide-brand-100">
          {balances.map((balance) => (
            <li
              key={`${balance.leave_type_id}-${balance.year}`}
              className="py-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-sm"
            >
              <span className="font-medium text-brand-900">
                {balance.leave_type_name}{" "}
                <span className="font-normal text-brand-300">({balance.year})</span>
              </span>
              <span className="text-xs text-brand-300">
                {balance.days_allowed} allowed · {balance.days_used} used · {balance.days_pending}{" "}
                pending · <span className="font-semibold text-brand-600">{balance.days_available} available</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </ApplicationSection>
  );
}

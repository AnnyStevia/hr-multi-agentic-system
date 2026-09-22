"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { BackLink } from "@/components/BackLink";
import { api } from "@/lib/api";
import type { LeavePolicy, LeaveType } from "@/types/leave";

export default function HrLeavePoliciesPage() {
  const [policies, setPolicies] = useState<LeavePolicy[]>([]);
  const [types, setTypes] = useState<LeaveType[]>([]);
  const [leaveTypeId, setLeaveTypeId] = useState("");
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [daysAllowed, setDaysAllowed] = useState("24");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [actingId, setActingId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDays, setEditDays] = useState("");
  const [error, setError] = useState("");

  const load = async () => {
    setError("");
    setLoading(true);
    try {
      const [policyRows, typeRows] = await Promise.all([
        api.listLeavePolicies(),
        api.listLeaveTypes(true),
      ]);
      setPolicies(policyRows);
      setTypes(typeRows);
      if (!leaveTypeId && typeRows.length > 0) {
        setLeaveTypeId(String(typeRows[0].id));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load policies");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await api.createLeavePolicy({
        leave_type_id: Number(leaveTypeId),
        year: Number(year),
        days_allowed: Number(daysAllowed),
      });
      setDaysAllowed("24");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create policy");
    } finally {
      setSubmitting(false);
    }
  };

  const startEdit = (policy: LeavePolicy) => {
    setEditingId(policy.id);
    setEditDays(String(policy.days_allowed));
    setError("");
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditDays("");
  };

  const handleSaveEdit = async (policyId: number) => {
    const days = Number(editDays);
    if (!Number.isFinite(days) || days < 0 || days > 365) {
      setError("Days allowed must be between 0 and 365");
      return;
    }
    setActingId(policyId);
    setError("");
    try {
      await api.updateLeavePolicy(policyId, { days_allowed: days });
      setEditingId(null);
      setEditDays("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update policy");
    } finally {
      setActingId(null);
    }
  };

  const handleDelete = async (policyId: number) => {
    if (!window.confirm("Delete this leave policy?")) return;
    setActingId(policyId);
    setError("");
    try {
      await api.deleteLeavePolicy(policyId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete policy");
    } finally {
      setActingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <BackLink href="/hr/leave" label="Leave" />
        <h1 className="mt-2 text-2xl font-bold text-brand-900">Leave policies</h1>
        <p className="mt-1 text-sm text-brand-300">
          Set yearly allowances by leave type. These are company-configured, not hard-coded.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm max-w-2xl">
          {error}
        </div>
      )}

      <form
        onSubmit={handleCreate}
        className="bg-white rounded-xl border border-brand-200 p-5 space-y-4 max-w-2xl"
      >
        {types.length === 0 ? (
          <p className="text-sm text-brand-300">
            Create an active leave type before adding a policy.{" "}
            <Link href="/hr/leave/types" className="text-brand-600 hover:text-brand-700">
              Manage types
            </Link>
          </p>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-brand-300 mb-1" htmlFor="policy-type">
                  Leave type
                </label>
                <select
                  id="policy-type"
                  value={leaveTypeId}
                  onChange={(e) => setLeaveTypeId(e.target.value)}
                  className="w-full border border-brand-100 rounded-lg px-3 py-2 text-sm text-brand-900 focus:outline-none focus:ring-2 focus:ring-brand-600/30"
                  required
                >
                  {types.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-brand-300 mb-1" htmlFor="policy-year">
                  Year
                </label>
                <input
                  id="policy-year"
                  type="number"
                  min={2000}
                  max={2100}
                  value={year}
                  onChange={(e) => setYear(e.target.value)}
                  className="w-full border border-brand-100 rounded-lg px-3 py-2 text-sm text-brand-900 focus:outline-none focus:ring-2 focus:ring-brand-600/30"
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-brand-300 mb-1" htmlFor="policy-days">
                  Days allowed
                </label>
                <input
                  id="policy-days"
                  type="number"
                  min={0}
                  max={365}
                  value={daysAllowed}
                  onChange={(e) => setDaysAllowed(e.target.value)}
                  className="w-full border border-brand-100 rounded-lg px-3 py-2 text-sm text-brand-900 focus:outline-none focus:ring-2 focus:ring-brand-600/30"
                  required
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={submitting}
              className="bg-brand-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
            >
              {submitting ? "Saving..." : "Create policy"}
            </button>
          </>
        )}
      </form>

      <div className="bg-white rounded-xl border border-brand-200 overflow-hidden max-w-2xl">
        {loading ? (
          <div className="py-16 flex justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
          </div>
        ) : policies.length === 0 ? (
          <p className="py-12 text-center text-sm text-brand-300">No policies configured yet.</p>
        ) : (
          <ul className="divide-y divide-brand-100">
            {policies.map((policy) => (
              <li key={policy.id} className="p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-brand-900">
                      {policy.leave_type_name} · {policy.year}
                    </p>
                    <p className="mt-0.5 text-sm text-brand-300">
                      {policy.days_allowed} days allowed
                    </p>
                  </div>
                  {editingId !== policy.id && (
                    <div className="flex gap-3 text-sm">
                      <button
                        type="button"
                        disabled={actingId === policy.id}
                        onClick={() => startEdit(policy)}
                        className="text-brand-600 hover:text-brand-700 disabled:opacity-50"
                      >
                        Edit days
                      </button>
                      <button
                        type="button"
                        disabled={actingId === policy.id}
                        onClick={() => handleDelete(policy.id)}
                        className="text-red-600 hover:text-red-700 disabled:opacity-50"
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </div>
                {editingId === policy.id && (
                  <form
                    className="mt-3 flex flex-wrap items-end gap-2 max-w-sm"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void handleSaveEdit(policy.id);
                    }}
                  >
                    <div className="flex-1 min-w-[7rem]">
                      <label className="block text-xs text-brand-300 mb-1" htmlFor={`edit-days-${policy.id}`}>
                        Days allowed
                      </label>
                      <input
                        id={`edit-days-${policy.id}`}
                        type="number"
                        min={0}
                        max={365}
                        value={editDays}
                        onChange={(e) => setEditDays(e.target.value)}
                        className="w-full border border-brand-100 rounded-lg px-3 py-1.5 text-sm text-brand-900 focus:outline-none focus:ring-2 focus:ring-brand-600/30"
                        autoFocus
                        required
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={actingId === policy.id}
                      className="bg-brand-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-brand-700 disabled:opacity-50"
                    >
                      {actingId === policy.id ? "Saving..." : "Save"}
                    </button>
                    <button
                      type="button"
                      onClick={cancelEdit}
                      className="border border-brand-100 text-brand-900 px-3 py-1.5 rounded-lg text-sm hover:bg-brand-50"
                    >
                      Cancel
                    </button>
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

"use client";

import { FormEvent, useEffect, useState } from "react";
import { BackLink } from "@/components/BackLink";
import { api } from "@/lib/api";
import type { LeaveType } from "@/types/leave";

export default function HrLeaveTypesPage() {
  const [types, setTypes] = useState<LeaveType[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isPaid, setIsPaid] = useState(true);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [actingId, setActingId] = useState<number | null>(null);
  const [error, setError] = useState("");

  const load = async () => {
    setError("");
    setLoading(true);
    try {
      setTypes(await api.listLeaveTypes());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load leave types");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await api.createLeaveType({
        name: name.trim(),
        description: description.trim() || null,
        is_paid: isPaid,
      });
      setName("");
      setDescription("");
      setIsPaid(true);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create leave type");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeactivate = async (id: number) => {
    setActingId(id);
    setError("");
    try {
      await api.deleteLeaveType(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to deactivate leave type");
    } finally {
      setActingId(null);
    }
  };

  const handleReactivate = async (id: number) => {
    setActingId(id);
    setError("");
    try {
      await api.updateLeaveType(id, { is_active: true });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reactivate leave type");
    } finally {
      setActingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <BackLink href="/hr/leave" label="Leave" />
        <h1 className="mt-2 text-2xl font-bold text-brand-900">Leave types</h1>
        <p className="mt-1 text-sm text-brand-300">Configure company leave categories.</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleCreate} className="bg-white rounded-xl border border-brand-200 p-5 space-y-4 max-w-2xl">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-brand-300 mb-1" htmlFor="type-name">
              Name
            </label>
            <input
              id="type-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border border-brand-200 rounded-lg px-3 py-2 text-sm text-brand-900 focus:outline-none focus:ring-2 focus:ring-brand-600/30"
              required
            />
          </div>
          <div className="flex items-end">
            <label className="inline-flex items-center gap-2 text-sm text-brand-900">
              <input
                type="checkbox"
                checked={isPaid}
                onChange={(e) => setIsPaid(e.target.checked)}
                className="accent-brand-600"
              />
              Paid leave
            </label>
          </div>
          <div className="sm:col-span-2">
            <label className="block text-xs text-brand-300 mb-1" htmlFor="type-description">
              Description
            </label>
            <textarea
              id="type-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full border border-brand-200 rounded-lg px-3 py-2 text-sm text-brand-900 focus:outline-none focus:ring-2 focus:ring-brand-600/30"
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="bg-brand-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
        >
          {submitting ? "Creating..." : "Create leave type"}
        </button>
      </form>

      <div className="bg-white rounded-xl border border-brand-200 overflow-hidden max-w-2xl">
        {loading ? (
          <div className="py-16 flex justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
          </div>
        ) : types.length === 0 ? (
          <p className="py-16 text-center text-sm text-brand-300">No leave types yet.</p>
        ) : (
          <ul className="divide-y divide-brand-100">
            {types.map((type) => (
              <li key={type.id} className="p-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-brand-900">{type.name}</p>
                  <p className="mt-1 text-xs text-brand-300">
                    {type.is_paid ? "Paid" : "Unpaid"} · {type.is_active ? "Active" : "Inactive"}
                  </p>
                  {type.description && (
                    <p className="mt-1 text-sm text-brand-300">{type.description}</p>
                  )}
                </div>
                {type.is_active ? (
                  <button
                    type="button"
                    disabled={actingId === type.id}
                    onClick={() => handleDeactivate(type.id)}
                    className="text-sm text-red-600 hover:text-red-700 disabled:opacity-50"
                  >
                    Deactivate
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={actingId === type.id}
                    onClick={() => handleReactivate(type.id)}
                    className="text-sm text-brand-600 hover:text-brand-700 disabled:opacity-50"
                  >
                    Reactivate
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

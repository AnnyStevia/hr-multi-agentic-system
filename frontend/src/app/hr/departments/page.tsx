"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Department } from "@/types/departments";

export default function DepartmentsPage() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [actingId, setActingId] = useState<number | null>(null);

  const load = async () => {
    setError("");
    setLoading(true);
    try {
      setDepartments(await api.listDepartments("all"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load departments");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await api.createDepartment(name);
      setName("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create department");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeactivate = async (id: number) => {
    setActingId(id);
    setError("");
    try {
      await api.deactivateDepartment(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to deactivate department");
    } finally {
      setActingId(null);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Departments</h1>
        <p className="mt-1 text-sm text-gray-600">Used by employees and job offers. Deactivating keeps existing records.</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{error}</div>
      )}

      <form onSubmit={handleCreate} className="bg-white rounded-xl border shadow-sm p-6 flex flex-col sm:flex-row gap-3">
        <input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Department name"
          className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-brand-500"
        />
        <button
          type="submit"
          disabled={submitting}
          className="bg-brand-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
        >
          {submitting ? "Adding..." : "Add department"}
        </button>
      </form>

      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-16 flex justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
          </div>
        ) : departments.length === 0 ? (
          <div className="py-16 text-center text-sm text-gray-500">No departments yet.</div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {departments.map((department) => (
                <tr key={department.id}>
                  <td className="px-4 py-3 text-sm text-gray-900">{department.name}</td>
                  <td className="px-4 py-3 text-sm capitalize">{department.status}</td>
                  <td className="px-4 py-3 text-right">
                    {department.status === "active" && (
                      <button
                        type="button"
                        disabled={actingId === department.id}
                        onClick={() => handleDeactivate(department.id)}
                        className="text-sm text-red-700 disabled:opacity-50"
                      >
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

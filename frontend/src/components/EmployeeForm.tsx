"use client";

import { FormEvent } from "react";
import type { Department } from "@/types/departments";
import type { Employee, EmployeePayload } from "@/types/employees";
import type { OrgPosition } from "@/types/organization";

const inputClass =
  "w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none transition";

export function EmployeeForm({
  values,
  departments,
  positions,
  managers,
  submitting,
  submitLabel,
  onChange,
  onSubmit,
}: {
  values: EmployeePayload;
  departments: Department[];
  positions: OrgPosition[];
  managers: Employee[];
  submitting: boolean;
  submitLabel: string;
  onChange: (values: EmployeePayload) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  const set = (field: keyof EmployeePayload, value: string | number | null) => {
    onChange({ ...values, [field]: value });
  };

  return (
    <form onSubmit={onSubmit} className="bg-white rounded-xl border shadow-sm p-6 space-y-5">
      <h2 className="text-sm font-medium text-gray-900">Personal information</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <label className="text-sm text-gray-700">
          First name
          <input required className={`${inputClass} mt-1`} value={values.first_name} onChange={(e) => set("first_name", e.target.value)} />
        </label>
        <label className="text-sm text-gray-700">
          Last name
          <input required className={`${inputClass} mt-1`} value={values.last_name} onChange={(e) => set("last_name", e.target.value)} />
        </label>
        <label className="text-sm text-gray-700">
          Email
          <input required type="email" className={`${inputClass} mt-1`} value={values.email} onChange={(e) => set("email", e.target.value)} />
        </label>
        <label className="text-sm text-gray-700">
          Phone
          <input required type="tel" minLength={8} maxLength={30} className={`${inputClass} mt-1`} value={values.phone} onChange={(e) => set("phone", e.target.value)} />
        </label>
      </div>
      <h2 className="text-sm font-medium text-gray-900">Employment information</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <label className="text-sm text-gray-700">
          Department
          <select
            required
            className={`${inputClass} mt-1`}
            value={values.department_id || ""}
            onChange={(e) => set("department_id", Number(e.target.value))}
          >
            <option value="">Select department</option>
            {departments.map((department) => (
              <option key={department.id} value={department.id}>
                {department.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-gray-700">
          Position
          <select
            required
            className={`${inputClass} mt-1`}
            value={values.position_id || ""}
            onChange={(e) => {
              const id = Number(e.target.value);
              const selected = positions.find((item) => item.id === id);
              onChange({
                ...values,
                position_id: id,
                position: selected?.title || values.position,
              });
            }}
          >
            <option value="">Select position</option>
            {positions.map((position) => (
              <option key={position.id} value={position.id}>
                {position.title}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-gray-700">
          Manager
          <select
            className={`${inputClass} mt-1`}
            value={values.manager_id ?? ""}
            onChange={(e) =>
              set("manager_id", e.target.value ? Number(e.target.value) : null)
            }
          >
            <option value="">No manager (top-level)</option>
            {managers.map((manager) => (
              <option key={manager.id} value={manager.id}>
                {manager.full_name} · {manager.position}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-gray-700">
          Hire date
          <input required type="date" className={`${inputClass} mt-1`} value={values.hire_date} onChange={(e) => set("hire_date", e.target.value)} />
        </label>
      </div>
      <button
        type="submit"
        disabled={submitting || departments.length === 0 || positions.length === 0}
        className="w-full bg-brand-600 text-white py-2.5 rounded-lg font-medium hover:bg-brand-700 disabled:opacity-50"
      >
        {submitting ? "Saving..." : submitLabel}
      </button>
      {positions.length === 0 && (
        <p className="text-xs text-amber-700">Create at least one position under Positions before saving.</p>
      )}
    </form>
  );
}

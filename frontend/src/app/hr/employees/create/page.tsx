"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { EmployeeForm } from "@/components/EmployeeForm";
import { api } from "@/lib/api";
import type { Department } from "@/types/departments";
import type { EmployeePayload } from "@/types/employees";

const emptyForm = (): EmployeePayload => ({
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  department_id: 0,
  position: "",
  hire_date: "",
});

export default function CreateEmployeePage() {
  const router = useRouter();
  const [values, setValues] = useState<EmployeePayload>(emptyForm());
  const [departments, setDepartments] = useState<Department[]>([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        setDepartments(await api.listDepartments("active"));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load departments");
      }
    };
    load();
  }, []);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const created = await api.createEmployee(values);
      router.push(`/hr/employees/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create employee");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <Link href="/hr/employees" className="text-sm text-gray-500 hover:text-gray-800">Employees</Link>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">Add employee</h1>
        <p className="mt-1 text-sm text-gray-600">No user account is created. Employee number is generated automatically.</p>
      </div>
      {error && <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{error}</div>}
      {departments.length === 0 && (
        <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 px-4 py-3 rounded-lg">
          Create an active department first. <Link href="/hr/departments" className="font-medium underline">Manage departments</Link>
        </p>
      )}
      <EmployeeForm
        values={values}
        departments={departments}
        submitting={submitting}
        submitLabel="Create employee"
        onChange={setValues}
        onSubmit={handleSubmit}
      />
    </div>
  );
}

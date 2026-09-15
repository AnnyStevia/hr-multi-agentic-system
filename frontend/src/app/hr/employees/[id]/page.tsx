"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApplicationSection } from "@/components/ApplicationSection";
import { EmployeeStatusBadge } from "@/components/EmployeeStatusBadge";
import { api } from "@/lib/api";
import type { Employee } from "@/types/employees";

export default function EmployeeProfilePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const employeeId = Number(params.id);
  const [employee, setEmployee] = useState<Employee | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [deactivating, setDeactivating] = useState(false);

  useEffect(() => {
    const load = async () => {
      setError("");
      setLoading(true);
      try {
        setEmployee(await api.getEmployee(employeeId));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load employee");
      } finally {
        setLoading(false);
      }
    };
    if (!Number.isNaN(employeeId)) load();
  }, [employeeId]);

  const handleDeactivate = async () => {
    if (!employee || employee.employment_status === "inactive") return;
    setDeactivating(true);
    setError("");
    try {
      setEmployee(await api.deactivateEmployee(employee.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to deactivate employee");
    } finally {
      setDeactivating(false);
    }
  };

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!employee) {
    return (
      <div className="max-w-4xl mx-auto">
        <p className="text-red-700">{error || "Employee not found"}</p>
        <button type="button" onClick={() => router.push("/hr/employees")} className="mt-4 text-sm text-brand-700">
          Back to employees
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link href="/hr/employees" className="text-sm text-gray-500 hover:text-gray-800">Employees</Link>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">{employee.full_name}</h1>
            <EmployeeStatusBadge status={employee.employment_status} />
          </div>
          <p className="mt-1 text-sm text-gray-600">{employee.employee_number}</p>
        </div>
        <div className="flex gap-3">
          <Link href={`/hr/employees/${employee.id}/edit`} className="border border-gray-300 px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-gray-50">
            Edit
          </Link>
          {employee.employment_status !== "inactive" && (
            <button
              type="button"
              disabled={deactivating}
              onClick={handleDeactivate}
              className="border border-red-200 text-red-700 px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-red-50 disabled:opacity-50"
            >
              {deactivating ? "Deactivating..." : "Deactivate"}
            </button>
          )}
        </div>
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{error}</div>}

      <ApplicationSection title="Employee information">
        <p className="text-sm text-gray-800">Employee number: {employee.employee_number}</p>
        <p className="text-sm text-gray-800">First name: {employee.first_name}</p>
        <p className="text-sm text-gray-800">Last name: {employee.last_name}</p>
        <p className="text-sm text-gray-800">Email: {employee.email}</p>
        <p className="text-sm text-gray-800">Phone: {employee.phone}</p>
      </ApplicationSection>

      <ApplicationSection title="Employment information">
        <p className="text-sm text-gray-800">Department: {employee.department}</p>
        <p className="text-sm text-gray-800">Position: {employee.position}</p>
        <p className="text-sm text-gray-800">Hire date: {employee.hire_date}</p>
        <p className="text-sm text-gray-800">Status: {employee.employment_status}</p>
      </ApplicationSection>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {["Documents", "Leave", "Training", "Evaluations"].map((label) => (
          <div key={label} className="bg-white rounded-xl border shadow-sm p-5">
            <p className="text-sm font-medium text-gray-900">{label}</p>
            <p className="mt-1 text-sm text-gray-500">Coming later</p>
          </div>
        ))}
      </div>
    </div>
  );
}

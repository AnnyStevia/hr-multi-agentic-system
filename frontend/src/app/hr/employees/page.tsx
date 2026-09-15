"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { EmployeeStatusBadge } from "@/components/EmployeeStatusBadge";
import { api } from "@/lib/api";
import type { Department } from "@/types/departments";
import type { Employee, EmploymentStatus } from "@/types/employees";

export default function EmployeesPage() {
  const [items, setItems] = useState<Employee[]>([]);
  const [total, setTotal] = useState(0);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<EmploymentStatus | "all">("active");
  const [departmentId, setDepartmentId] = useState<number | "">("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async (search = q, selectedStatus = status, selectedDepartment = departmentId) => {
    setError("");
    setLoading(true);
    try {
      const result = await api.listEmployees({
        q: search || undefined,
        status: selectedStatus,
        department_id: selectedDepartment === "" ? undefined : Number(selectedDepartment),
      });
      setItems(result.items);
      setTotal(result.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load employees");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const bootstrap = async () => {
      try {
        setDepartments(await api.listDepartments("all"));
      } catch {
        setDepartments([]);
      }
      await load();
    };
    bootstrap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearch = (event: FormEvent) => {
    event.preventDefault();
    load();
  };

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Employees</h1>
          <p className="mt-1 text-sm text-gray-600">{total} matching {status === "all" ? "employees" : `${status} employees`}.</p>
        </div>
        <Link href="/hr/employees/create" className="inline-flex justify-center bg-brand-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brand-700">
          Add Employee
        </Link>
      </div>

      <form onSubmit={handleSearch} className="bg-white rounded-xl border shadow-sm p-4 mb-4 grid grid-cols-1 md:grid-cols-4 gap-3">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search name or employee number"
          className="px-4 py-2.5 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-brand-500"
        />
        <select
          value={departmentId}
          onChange={(e) => setDepartmentId(e.target.value ? Number(e.target.value) : "")}
          className="px-4 py-2.5 border border-gray-300 rounded-lg"
        >
          <option value="">All departments</option>
          {departments.map((department) => (
            <option key={department.id} value={department.id}>{department.name}</option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as EmploymentStatus | "all")}
          className="px-4 py-2.5 border border-gray-300 rounded-lg"
        >
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="on_leave">On leave</option>
          <option value="all">All statuses</option>
        </select>
        <button type="submit" className="bg-gray-900 text-white px-4 py-2.5 rounded-lg text-sm font-medium">
          Filter
        </button>
      </form>

      {error && <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{error}</div>}

      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-16 flex justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
          </div>
        ) : items.length === 0 ? (
          <div className="py-16 text-center text-sm text-gray-500">No employees found.</div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Number</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Department</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Position</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Hire date</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {items.map((employee) => (
                <tr key={employee.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm text-gray-900">{employee.employee_number}</td>
                  <td className="px-4 py-3 text-sm">
                    <Link href={`/hr/employees/${employee.id}`} className="text-brand-700">{employee.full_name}</Link>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">{employee.email}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{employee.department}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{employee.position}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{employee.hire_date}</td>
                  <td className="px-4 py-3"><EmployeeStatusBadge status={employee.employment_status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

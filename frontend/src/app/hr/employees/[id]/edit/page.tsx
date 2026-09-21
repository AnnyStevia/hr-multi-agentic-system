"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { EmployeeForm } from "@/components/EmployeeForm";
import { api } from "@/lib/api";
import type { Department } from "@/types/departments";
import type { Employee, EmployeePayload } from "@/types/employees";
import type { OrgPosition } from "@/types/organization";

export default function EditEmployeePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const employeeId = Number(params.id);
  const [values, setValues] = useState<EmployeePayload | null>(null);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [positions, setPositions] = useState<OrgPosition[]>([]);
  const [managers, setManagers] = useState<Employee[]>([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const [employee, activeDepartments, pos, employees] = await Promise.all([
          api.getEmployee(employeeId),
          api.listDepartments("active"),
          api.listPositions(),
          api.listEmployees({ status: "active" }),
        ]);
        setValues({
          first_name: employee.first_name,
          last_name: employee.last_name,
          email: employee.email,
          phone: employee.phone,
          department_id: employee.department_id,
          position: employee.position,
          position_id: employee.position_id,
          manager_id: employee.manager_id,
          hire_date: employee.hire_date,
        });
        const current = activeDepartments.find((item) => item.id === employee.department_id);
        if (!current) {
          setDepartments([
            {
              id: employee.department_id,
              name: employee.department,
              status: "inactive",
              created_at: "",
              updated_at: "",
            },
            ...activeDepartments,
          ]);
        } else {
          setDepartments(activeDepartments);
        }
        setPositions(pos);
        setManagers(employees.items.filter((item) => item.id !== employeeId));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load employee");
      }
    };
    if (!Number.isNaN(employeeId)) load();
  }, [employeeId]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!values) return;
    setError("");
    setSubmitting(true);
    try {
      await api.updateEmployee(employeeId, {
        first_name: values.first_name,
        last_name: values.last_name,
        email: values.email,
        phone: values.phone,
        department_id: values.department_id,
        position_id: values.position_id ?? undefined,
        manager_id: values.manager_id ?? null,
        hire_date: values.hire_date,
      });
      router.push(`/hr/employees/${employeeId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update employee");
    } finally {
      setSubmitting(false);
    }
  };

  if (!values && !error) {
    return (
      <div className="py-16 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <Link href={`/hr/employees/${employeeId}`} className="text-sm text-gray-500 hover:text-gray-800">
          Profile
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">Edit employee</h1>
      </div>
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}
      {values && (
        <EmployeeForm
          values={values}
          departments={departments}
          positions={positions}
          managers={managers}
          submitting={submitting}
          submitLabel="Save changes"
          onChange={setValues}
          onSubmit={handleSubmit}
        />
      )}
    </div>
  );
}

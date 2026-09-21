"use client";

import type { EmployeeOrganization } from "@/types/organization";

export function EmployeeOrganizationCard({
  organization,
  title = "Organization",
}: {
  organization: EmployeeOrganization;
  title?: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-3">
      <h2 className="text-sm font-medium text-gray-900">{title}</h2>
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-xs text-gray-500">Employee</dt>
          <dd className="mt-0.5 text-gray-900">{organization.employee.full_name}</dd>
        </div>
        <div>
          <dt className="text-xs text-gray-500">Position</dt>
          <dd className="mt-0.5 text-gray-900">
            {organization.position?.title || organization.employee.position || "—"}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-gray-500">Department</dt>
          <dd className="mt-0.5 text-gray-900">
            {organization.department?.name || organization.employee.department || "—"}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-gray-500">Reports to</dt>
          <dd className="mt-0.5 text-gray-900">
            {organization.manager
              ? `${organization.manager.full_name}${
                  organization.manager.position ? ` · ${organization.manager.position}` : ""
                }`
              : "—"}
          </dd>
        </div>
      </dl>
    </div>
  );
}

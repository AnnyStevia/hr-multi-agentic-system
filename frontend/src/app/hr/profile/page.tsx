"use client";

import { EmployeeProfileSection } from "@/components/EmployeeProfileSection";

export default function HrProfilePage() {
  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">My profile</h1>
        <p className="mt-1 text-sm text-gray-600">
          Keep your personal information, education, and experience up to date.
        </p>
      </div>
      <EmployeeProfileSection mode="employee" />
    </div>
  );
}

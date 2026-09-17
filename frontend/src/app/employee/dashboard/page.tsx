"use client";

import { useAuth } from "@/hooks/useAuth";

export default function EmployeeDashboardPage() {
  const { user } = useAuth();

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900">Welcome, {user?.first_name}</h1>
      <p className="mt-2 text-gray-600">
        Your employee workspace will be expanded in a later phase.
      </p>
    </div>
  );
}

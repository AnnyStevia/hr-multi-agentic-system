"use client";

import { useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { hasRole } from "@/lib/roles";

export default function RoleStubDashboard({
  role,
  title,
}: {
  role: string;
  title: string;
}) {
  const { user, loading, logout } = useAuth();

  useEffect(() => {
    if (!loading && !user) {
      window.location.href = "/login";
    }
  }, [loading, user]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!user) return null;

  if (!hasRole(user, role)) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="bg-white rounded-xl shadow-sm border p-8 max-w-md text-center">
          <h1 className="text-xl font-bold text-gray-900">Access denied</h1>
          <p className="mt-2 text-sm text-gray-600">
            This portal is reserved for {role} users.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900">{title}</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600">{user.full_name}</span>
            <button
              onClick={logout}
              className="text-sm text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-50 transition"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h2 className="text-2xl font-bold text-gray-900">Welcome, {user.first_name}</h2>
        <p className="mt-2 text-gray-600">
          This {role} workspace will be expanded in a later phase.
        </p>
      </main>
    </div>
  );
}

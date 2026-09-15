"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { getHomePath, isAdmin, isHR } from "@/lib/roles";

export default function DashboardPage() {
  const { user, loading, logout } = useAuth();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      window.location.href = "/login";
      return;
    }
    const home = getHomePath(user);
    if (home !== "/dashboard") {
      window.location.replace(home);
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

  return (
    <div className="min-h-screen">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900">HR Platform</h1>
          <div className="flex items-center gap-4">
            {(isHR(user) || isAdmin(user)) && (
              <>
                <Link
                  href="/hr/jobs"
                  className="text-sm text-brand-700 px-3 py-1.5 rounded-lg border border-brand-200 hover:bg-brand-50"
                >
                  Job offers
                </Link>
                <Link
                  href="/hr/jobs/create"
                  className="text-sm bg-brand-600 text-white px-3 py-1.5 rounded-lg hover:bg-brand-700"
                >
                  Create job
                </Link>
              </>
            )}
            <span className="text-sm text-gray-600">{user.full_name}</span>
            <button
              onClick={logout}
              className="text-sm text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-50"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h2 className="text-2xl font-bold text-gray-900">Welcome, {user.first_name}</h2>
        <p className="mt-1 text-gray-600">Redirecting you to your portal…</p>

        {(isHR(user) || isAdmin(user)) && (
          <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-4">
            <Link
              href="/hr/dashboard"
              className="block bg-white rounded-xl border-2 border-brand-200 p-6 hover:border-brand-500"
            >
              <p className="text-lg font-semibold text-gray-900">Open HR portal</p>
              <p className="mt-1 text-sm text-gray-600">
                Dashboard, recruitment, and job offers.
              </p>
            </Link>
            <Link
              href="/hr/jobs/create"
              className="block bg-white rounded-xl border-2 border-brand-200 p-6 hover:border-brand-500"
            >
              <p className="text-lg font-semibold text-gray-900">Create Job Offer</p>
              <p className="mt-1 text-sm text-gray-600">
                Save as draft or publish a recruitment offer.
              </p>
            </Link>
          </div>
        )}
      </main>
    </div>
  );
}

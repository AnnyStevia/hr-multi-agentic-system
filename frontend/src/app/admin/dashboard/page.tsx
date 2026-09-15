"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { isAdmin } from "@/lib/roles";

export default function AdminDashboardPage() {
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

  if (!isAdmin(user)) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="bg-white rounded-xl shadow-sm border p-8 max-w-md text-center">
          <h1 className="text-xl font-bold text-gray-900">Access denied</h1>
          <p className="mt-2 text-sm text-gray-600">
            Only administrators can access this dashboard.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900">Admin Portal</h1>
          <div className="flex items-center gap-4">
            <Link
              href="/admin/accounts"
              className="text-sm text-brand-700 px-3 py-1.5 rounded-lg border border-brand-200 hover:bg-brand-50 transition"
            >
              Accounts
            </Link>
            <Link
              href="/hr/jobs"
              className="text-sm text-brand-700 px-3 py-1.5 rounded-lg border border-brand-200 hover:bg-brand-50 transition"
            >
              Job offers
            </Link>
            <Link
              href="/hr/jobs/create"
              className="text-sm bg-brand-600 text-white px-3 py-1.5 rounded-lg hover:bg-brand-700 transition"
            >
              Create job
            </Link>
            <Link
              href="/admin/hr/create"
              className="text-sm text-gray-700 px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-50 transition"
            >
              Create HR account
            </Link>
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

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900">
            Welcome, {user.first_name}
          </h2>
          <p className="mt-1 text-gray-600">
            You are signed in as a platform administrator.
          </p>
        </div>

        <section className="mb-8">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">
            Administration
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link
              href="/admin/accounts"
              className="block bg-white rounded-xl shadow-sm border-2 border-brand-200 p-6 hover:border-brand-500 hover:shadow-md transition"
            >
              <p className="text-lg font-semibold text-gray-900">View accounts</p>
              <p className="mt-1 text-sm text-gray-600">
                See every platform account and download the list as Excel.
              </p>
            </Link>
            <Link
              href="/admin/hr/create"
              className="block bg-white rounded-xl shadow-sm border-2 border-brand-200 p-6 hover:border-brand-500 hover:shadow-md transition"
            >
              <p className="text-lg font-semibold text-gray-900">Create HR account</p>
              <p className="mt-1 text-sm text-gray-600">
                Add a Human Resources user. The HR role is assigned automatically.
              </p>
            </Link>
            <Link
              href="/hr/jobs"
              className="block bg-white rounded-xl shadow-sm border-2 border-brand-200 p-6 hover:border-brand-500 hover:shadow-md transition"
            >
              <p className="text-lg font-semibold text-gray-900">Job offers</p>
              <p className="mt-1 text-sm text-gray-600">
                Create, publish, and close recruitment job offers.
              </p>
            </Link>
          </div>
        </section>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">
              Profile
            </h3>
            <dl className="mt-4 space-y-3">
              <div>
                <dt className="text-xs text-gray-500">Email</dt>
                <dd className="text-sm font-medium text-gray-900">{user.email}</dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500">Full Name</dt>
                <dd className="text-sm font-medium text-gray-900">{user.full_name}</dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500">Status</dt>
                <dd>
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                    Active
                  </span>
                </dd>
              </div>
            </dl>
          </div>

          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">
              Roles
            </h3>
            <div className="mt-4 flex flex-wrap gap-2">
              {user.roles.map((role) => (
                <span
                  key={role.id}
                  className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-brand-100 text-brand-800"
                >
                  {role.name}
                </span>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border p-6">
            <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">
              Permissions
            </h3>
            <div className="mt-4 flex flex-wrap gap-1.5 max-h-48 overflow-y-auto">
              {user.permissions.map((perm) => (
                <span
                  key={perm}
                  className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono bg-gray-100 text-gray-700"
                >
                  {perm}
                </span>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

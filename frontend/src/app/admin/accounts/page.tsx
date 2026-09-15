"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import { isAdmin } from "@/lib/roles";
import type { Account } from "@/types/auth";

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function AccountsPage() {
  const { user, loading, logout } = useAuth();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [error, setError] = useState("");
  const [loadingAccounts, setLoadingAccounts] = useState(true);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (!loading && !user) {
      window.location.href = "/login";
    }
  }, [loading, user]);

  useEffect(() => {
    if (!user || !isAdmin(user)) return;

    const loadAccounts = async () => {
      setError("");
      setLoadingAccounts(true);
      try {
        const data = await api.listAccounts();
        setAccounts(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load accounts");
      } finally {
        setLoadingAccounts(false);
      }
    };

    loadAccounts();
  }, [user]);

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
            Only administrators can view platform accounts.
          </p>
          <Link
            href="/admin/dashboard"
            className="inline-block mt-6 text-sm text-brand-600 hover:text-brand-700"
          >
            Back to dashboard
          </Link>
        </div>
      </div>
    );
  }

  const handleDownload = async () => {
    setError("");
    setDownloading(true);
    try {
      await api.downloadAccountsExcel();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download Excel file");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="min-h-screen">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/admin/dashboard" className="text-sm text-gray-600 hover:text-gray-900">
              Dashboard
            </Link>
            <h1 className="text-xl font-bold text-gray-900">Accounts</h1>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/admin/hr/create"
              className="text-sm text-brand-700 px-3 py-1.5 rounded-lg border border-brand-200 hover:bg-brand-50 transition"
            >
              Create HR account
            </Link>
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
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Platform accounts</h2>
            <p className="mt-1 text-sm text-gray-600">
              {loadingAccounts ? "Loading accounts..." : `${accounts.length} account(s)`}
            </p>
          </div>
          <button
            onClick={handleDownload}
            disabled={downloading || loadingAccounts || accounts.length === 0}
            className="bg-brand-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {downloading ? "Downloading..." : "Download Excel"}
          </button>
        </div>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        )}

        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
          {loadingAccounts ? (
            <div className="py-16 flex justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Name
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Email
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Roles
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Created
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {accounts.map((account) => (
                    <tr key={account.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">
                        {account.full_name}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700">{account.email}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1.5">
                          {account.roles.map((role) => (
                            <span
                              key={role.id}
                              className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-brand-100 text-brand-800"
                            >
                              {role.name}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            account.is_active
                              ? "bg-green-100 text-green-800"
                              : "bg-red-100 text-red-800"
                          }`}
                        >
                          {account.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                        {formatDate(account.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

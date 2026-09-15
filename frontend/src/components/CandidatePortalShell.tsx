"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { NotificationBell } from "@/components/NotificationBell";
import { useAuth } from "@/hooks/useAuth";
import { isCandidate } from "@/lib/roles";

export function CandidatePortalShell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) {
      const next = pathname || "/careers/jobs";
      window.location.href = `/login?next=${encodeURIComponent(next)}`;
    }
  }, [loading, user, pathname]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!user) return null;

  if (!isCandidate(user)) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="bg-white rounded-xl shadow-sm border p-8 max-w-md text-center">
          <h1 className="text-xl font-bold text-gray-900">Access denied</h1>
          <p className="mt-2 text-sm text-gray-600">
            Only candidates can browse published job openings here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div>
            <Link href="/careers/jobs" className="text-xl font-bold text-gray-900">
              Careers
            </Link>
            <p className="text-xs text-gray-500 mt-0.5">Published openings</p>
          </div>
          <div className="flex items-center gap-4">
            <NotificationBell />
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
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">{children}</main>
    </div>
  );
}

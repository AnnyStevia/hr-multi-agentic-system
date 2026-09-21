"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { NotificationBell } from "@/components/NotificationBell";
import { UserMenu } from "@/components/UserMenu";
import { useAuth } from "@/hooks/useAuth";
import { isCandidate, needsOnboarding } from "@/lib/roles";

export function CandidatePortalShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) {
      const next = pathname || "/careers/jobs";
      window.location.href = `/login?next=${encodeURIComponent(next)}`;
      return;
    }
    if (!loading && user && needsOnboarding(user)) {
      window.location.href = "/employee/onboarding";
    }
  }, [loading, user, pathname]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!user) return null;

  if (needsOnboarding(user)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!isCandidate(user)) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 bg-slate-50">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 max-w-md text-center">
          <h1 className="text-xl font-bold text-gray-900">Access denied</h1>
          <p className="mt-2 text-sm text-gray-600">
            Only candidates can browse published job openings here.
          </p>
        </div>
      </div>
    );
  }

  const jobsActive = pathname === "/careers/jobs" || pathname.startsWith("/careers/jobs/");

  return (
    <div className="min-h-screen flex bg-slate-50">
      <aside className="w-56 bg-white border-r border-gray-200 flex flex-col shrink-0">
        <div className="px-5 py-5 border-b border-gray-100">
          <p className="text-sm font-semibold tracking-tight text-gray-900">Careers</p>
          <p className="mt-0.5 text-xs text-gray-500">Open roles</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          <Link
            href="/careers/jobs"
            className={`block px-3 py-2 rounded-md text-sm transition ${
              jobsActive
                ? "bg-brand-50 text-brand-700 font-medium"
                : "text-gray-600 hover:bg-slate-50 hover:text-gray-900"
            }`}
          >
            Jobs
          </Link>
        </nav>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white border-b border-gray-200">
          <div className="px-6 h-14 flex items-center justify-end gap-3">
            <NotificationBell />
            <UserMenu />
          </div>
        </header>
        <main className="flex-1 px-6 py-8 max-w-5xl w-full mx-auto">{children}</main>
      </div>
    </div>
  );
}

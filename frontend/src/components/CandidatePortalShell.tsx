"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { Briefcase } from "lucide-react";
import { NotificationBell } from "@/components/NotificationBell";
import { UserMenu } from "@/components/UserMenu";
import { useAuth } from "@/hooks/useAuth";
import { isCandidate, needsOnboarding } from "@/lib/roles";
import { cn } from "@/lib/utils";

export function CandidatePortalShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) {
      const next = pathname || "/careers/jobs";
      window.location.href = `/careers/login?next=${encodeURIComponent(next)}`;
      return;
    }
    if (!loading && user && needsOnboarding(user)) {
      window.location.href = "/employee/onboarding";
    }
  }, [loading, user, pathname]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f3f6f5]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
      </div>
    );
  }

  if (!user) return null;

  if (needsOnboarding(user)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f3f6f5]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
      </div>
    );
  }

  if (!isCandidate(user)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f3f6f5] px-4">
        <div className="max-w-md rounded-2xl border border-brand-200/70 bg-white p-8 text-center shadow-sm">
          <h1 className="text-xl font-semibold text-brand-900">Access denied</h1>
          <p className="mt-2 text-sm text-brand-300">
            Only candidates can browse published job openings here.
          </p>
        </div>
      </div>
    );
  }

  const jobsActive =
    pathname === "/careers/jobs" || pathname.startsWith("/careers/jobs/");

  return (
    <div className="flex min-h-screen bg-[#f3f6f5]">
      <aside className="flex w-[15.5rem] shrink-0 flex-col border-r border-brand-200/60 bg-[#f7faf9]">
        <div className="flex items-center gap-2.5 px-4 py-5">
          <span className="relative flex h-9 w-9 items-center justify-center">
            <span className="absolute inset-1 rotate-45 rounded-md bg-brand-600" />
            <span className="absolute inset-[7px] rotate-45 rounded-[3px] bg-emerald-400/90" />
            <span className="relative h-2 w-2 rotate-45 rounded-[1px] bg-white" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-[15px] font-semibold tracking-tight text-brand-900">
              Careers
            </p>
            <p className="truncate text-[11px] text-brand-300">Open roles</p>
          </div>
        </div>

        <nav className="flex-1 px-3 py-2">
          <Link
            href="/careers/jobs"
            className={cn(
              "flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium transition",
              jobsActive
                ? "bg-emerald-50 text-brand-700"
                : "text-brand-300 hover:bg-white hover:text-brand-700"
            )}
          >
            <Briefcase className="size-4 shrink-0" />
            Jobs
          </Link>
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-end gap-3 border-b border-brand-200/60 bg-white/80 px-5 backdrop-blur-sm sm:px-6">
          <NotificationBell />
          <UserMenu />
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}

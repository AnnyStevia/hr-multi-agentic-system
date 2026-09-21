"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { NotificationBell } from "@/components/NotificationBell";
import { UserMenu } from "@/components/UserMenu";
import { useAuth } from "@/hooks/useAuth";
import { canAccessEmployeePortal, needsOnboarding } from "@/lib/roles";

const ONBOARDING_ALLOWED = new Set(["/employee/onboarding", "/employee/profile"]);

export default function EmployeeLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const allowDuringOnboarding = ONBOARDING_ALLOWED.has(pathname);
  const onboarding = needsOnboarding(user);

  useEffect(() => {
    if (!loading && !user) {
      window.location.href = "/login";
      return;
    }
    if (!loading && user && needsOnboarding(user) && !allowDuringOnboarding) {
      window.location.href = "/employee/onboarding";
    }
  }, [loading, user, allowDuringOnboarding]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!user) return null;

  if (!canAccessEmployeePortal(user)) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 bg-slate-50">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 max-w-md text-center">
          <h1 className="text-xl font-bold text-gray-900">Access denied</h1>
          <p className="mt-2 text-sm text-gray-600">This portal is reserved for employees.</p>
        </div>
      </div>
    );
  }

  if (onboarding && !allowDuringOnboarding) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex bg-slate-50">
      <aside className="w-56 bg-white border-r border-gray-200 flex flex-col shrink-0">
        <div className="px-5 py-5 border-b border-gray-100">
          <p className="text-sm font-semibold tracking-tight text-gray-900">Employee</p>
          <p className="mt-0.5 text-xs text-gray-500">
            {onboarding ? "Onboarding in progress" : "Workspace"}
          </p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {!onboarding && (
            <>
              <SideLink href="/employee/dashboard" pathname={pathname} label="Dashboard" />
              <SideLink href="/employee/organization" pathname={pathname} label="Organization" />
            </>
          )}
          <SideLink href="/employee/onboarding" pathname={pathname} label="Onboarding" />
        </nav>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white border-b border-gray-200">
          <div className="px-6 h-14 flex items-center justify-end gap-3">
            <NotificationBell variant="employee" />
            <UserMenu editProfileHref="/employee/profile" />
          </div>
        </header>
        <main className="flex-1 px-6 py-8 max-w-5xl w-full mx-auto">{children}</main>
      </div>
    </div>
  );
}

function SideLink({
  href,
  pathname,
  label,
}: {
  href: string;
  pathname: string;
  label: string;
}) {
  const active = pathname === href || pathname.startsWith(`${href}/`);
  return (
    <Link
      href={href}
      className={`block px-3 py-2 rounded-md text-sm transition ${
        active
          ? "bg-brand-50 text-brand-700 font-medium"
          : "text-gray-600 hover:bg-slate-50 hover:text-gray-900"
      }`}
    >
      {label}
    </Link>
  );
}

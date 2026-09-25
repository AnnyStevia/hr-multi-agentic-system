"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import {
  AIAssistantMain,
  AIAssistantProvider,
  AIAwareTopBar,
  FloatingAIButton,
} from "@/components/ai-assistant";
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
      <div className="min-h-screen flex items-center justify-center bg-brand-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!user) return null;

  if (!canAccessEmployeePortal(user)) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 bg-brand-50">
        <div className="bg-white rounded-xl border border-brand-200 p-8 max-w-md text-center">
          <h1 className="text-xl font-bold text-brand-900">Access denied</h1>
          <p className="mt-2 text-sm text-brand-300">This portal is reserved for employees.</p>
        </div>
      </div>
    );
  }

  if (onboarding && !allowDuringOnboarding) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-brand-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  return (
    <AIAssistantProvider>
      <div className="h-screen overflow-hidden flex bg-brand-50">
        <aside className="w-56 h-full shrink-0 overflow-y-auto bg-white border-r border-brand-200 flex flex-col">
          <div className="px-5 py-5 border-b border-brand-200 shrink-0">
            <p className="text-sm font-semibold tracking-tight text-brand-900">Employee</p>
            <p className="mt-0.5 text-xs text-brand-300">
              {onboarding ? "Onboarding in progress" : "Workspace"}
            </p>
          </div>
          <nav className="flex-1 px-3 py-4 space-y-0.5">
            {!onboarding && (
              <>
                <SideLink href="/employee/dashboard" pathname={pathname} label="Dashboard" />
                <SideLink href="/employee/organization" pathname={pathname} label="Organization" />
                <SideLink href="/employee/leave" pathname={pathname} label="Leave" />
                <SideLink href="/employee/documents" pathname={pathname} label="Documents" />
              </>
            )}
            <SideLink href="/employee/onboarding" pathname={pathname} label="Onboarding" />
          </nav>
        </aside>

        <div className="flex-1 flex flex-col min-w-0 min-h-0 h-full">
          <AIAwareTopBar
            notificationVariant="employee"
            editProfileHref="/employee/profile"
          />
          <AIAssistantMain contentClassName="flex-1 min-h-0 overflow-y-auto px-6 py-8">
            <div className="max-w-5xl w-full mx-auto">{children}</div>
          </AIAssistantMain>
        </div>
      </div>
      <FloatingAIButton />
    </AIAssistantProvider>
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
          ? "bg-brand-100 text-brand-900 font-medium"
          : "text-brand-900 hover:bg-brand-100"
      }`}
    >
      {label}
    </Link>
  );
}

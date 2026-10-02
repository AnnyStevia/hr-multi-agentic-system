"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo } from "react";
import {
  ArrowLeft,
  CalendarDays,
  FileText,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Network,
  Palmtree,
  Send,
  UserPlus,
} from "lucide-react";
import {
  AIAssistantMain,
  AIAssistantProvider,
  AIAwareTopBar,
  FloatingAIButton,
} from "@/components/ai-assistant";
import {
  GlassPortalShell,
  GlassSidebar,
  type GlassNavItem,
} from "@/components/GlassSidebar";
import { useAuth } from "@/hooks/useAuth";
import {
  canAccessEmployeePortal,
  canAccessInterviewAssignments,
  getHomePath,
  isInterviewAssignmentsOnly,
  needsOnboarding,
} from "@/lib/roles";

const ONBOARDING_ALLOWED = new Set([
  "/employee/onboarding",
  "/employee/profile",
  "/employee/training",
]);

function isInterviewAssignmentsPath(pathname: string): boolean {
  return (
    pathname === "/employee/interviews" ||
    pathname.startsWith("/employee/interviews/")
  );
}

function hasHrHome(path: string): boolean {
  return path.startsWith("/hr");
}

export default function EmployeeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const allowDuringOnboarding = ONBOARDING_ALLOWED.has(pathname);
  const onboarding = needsOnboarding(user);
  const interviewOnly = isInterviewAssignmentsOnly(user);
  const onInterviewPath = isInterviewAssignmentsPath(pathname);

  useEffect(() => {
    if (!loading && !user) {
      window.location.href = "/login";
      return;
    }
    if (!loading && user && needsOnboarding(user) && !allowDuringOnboarding) {
      window.location.href = "/employee/onboarding";
      return;
    }
    if (!loading && user && interviewOnly && !onInterviewPath) {
      window.location.href = "/employee/interviews";
    }
  }, [loading, user, allowDuringOnboarding, interviewOnly, onInterviewPath]);

  const homePath = getHomePath(user);

  const navItems = useMemo((): GlassNavItem[] => {
    if (interviewOnly) {
      return [
        {
          href: "/employee/interviews",
          label: "My interviews",
          icon: CalendarDays,
        },
        {
          href: homePath,
          label: hasHrHome(homePath) ? "Back to HR" : "Back to home",
          icon: ArrowLeft,
          exact: true,
        },
      ];
    }

    const items: GlassNavItem[] = [];
    if (!onboarding) {
      items.push(
        { href: "/employee/dashboard", label: "Dashboard", icon: LayoutDashboard },
        { href: "/employee/organization", label: "Organization", icon: Network },
        { href: "/employee/interviews", label: "Interviews", icon: CalendarDays },
        { href: "/employee/leave", label: "Leave", icon: Palmtree },
        { href: "/employee/documents", label: "Documents", icon: FileText },
        {
          href: "/employee/offboarding",
          label: "Offboarding",
          icon: LogOut,
          exact: true,
        },
        {
          href: "/employee/offboarding/request",
          label: "Resignation request",
          icon: Send,
          nested: true,
        },
      );
    }
    items.push(
      { href: "/employee/training", label: "Training", icon: GraduationCap },
      { href: "/employee/onboarding", label: "Onboarding", icon: UserPlus },
    );
    return items;
  }, [interviewOnly, onboarding, homePath]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#061510]">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-brand-500" />
      </div>
    );
  }

  if (!user) return null;

  const allowed =
    canAccessEmployeePortal(user) ||
    (canAccessInterviewAssignments(user) && onInterviewPath);

  if (!allowed) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#061510] px-4">
        <div className="max-w-md rounded-xl border border-brand-200 bg-white p-8 text-center">
          <h1 className="text-xl font-bold text-brand-900">Access denied</h1>
          <p className="mt-2 text-sm text-brand-300">
            This portal is reserved for employees.
          </p>
          {canAccessInterviewAssignments(user) && (
            <Link
              href="/employee/interviews"
              className="mt-4 inline-block text-sm font-medium text-brand-700 underline underline-offset-2"
            >
              Go to interview assignments
            </Link>
          )}
        </div>
      </div>
    );
  }

  if (onboarding && !allowDuringOnboarding) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#061510]">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-brand-500" />
      </div>
    );
  }

  const notificationVariant = interviewOnly ? "hr" : "employee";
  const editProfileHref = interviewOnly ? "/hr/profile" : "/employee/profile";

  return (
    <AIAssistantProvider>
      <GlassPortalShell
        sidebar={
          <GlassSidebar
            title={interviewOnly ? "Interviewer" : "Employee"}
            subtitle={
              interviewOnly
                ? "Assignments"
                : onboarding
                  ? "Onboarding"
                  : "Workspace"
            }
            items={navItems}
            pathname={pathname}
            storageKey="employee-sidebar-collapsed"
          />
        }
      >
        <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col">
          <AIAwareTopBar
            notificationVariant={notificationVariant}
            editProfileHref={editProfileHref}
          />
          <AIAssistantMain contentClassName="flex-1 min-h-0 overflow-y-auto px-6 py-8">
            <div className="mx-auto w-full max-w-5xl">{children}</div>
          </AIAssistantMain>
        </div>
      </GlassPortalShell>
      <FloatingAIButton />
    </AIAssistantProvider>
  );
}

"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import {
  Briefcase,
  Building2,
  CalendarDays,
  ClipboardList,
  FileText,
  GraduationCap,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Megaphone,
  Network,
  Palmtree,
  UserPlus,
  Users,
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
import { canAccessHrPortal } from "@/lib/roles";

const CORE_NAV_ITEMS: GlassNavItem[] = [
  { href: "/hr/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/hr/employees", label: "Employees", icon: Users },
  { href: "/hr/departments", label: "Departments", icon: Building2 },
  { href: "/hr/positions", label: "Positions", icon: Briefcase },
  { href: "/hr/organization", label: "Organization", icon: Network },
  { href: "/hr/jobs", label: "Job Offers", icon: Megaphone },
  { href: "/employee/interviews", label: "My interviews", icon: CalendarDays },
  {
    href: "/hr/onboarding",
    label: "Onboarding",
    icon: UserPlus,
    isActive: (pathname) =>
      (pathname === "/hr/onboarding" || pathname.startsWith("/hr/onboarding/")) &&
      !pathname.startsWith("/hr/onboarding/templates"),
  },
  {
    href: "/hr/onboarding/templates",
    label: "Task catalogue",
    icon: ListChecks,
  },
  {
    href: "/hr/offboarding",
    label: "Offboarding",
    icon: LogOut,
    isActive: (pathname) =>
      (pathname === "/hr/offboarding" ||
        pathname.startsWith("/hr/offboarding/")) &&
      !pathname.startsWith("/hr/offboarding/requests"),
  },
  {
    href: "/hr/offboarding/requests",
    label: "Offboarding requests",
    icon: ClipboardList,
  },
  { href: "/hr/training", label: "Training", icon: GraduationCap },
  { href: "/hr/leave", label: "Leave", icon: Palmtree },
  { href: "/hr/documents", label: "Documents", icon: FileText },
];

export default function HrLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) {
      window.location.href = "/login";
    }
  }, [loading, user]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#061510]">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-brand-500" />
      </div>
    );
  }

  if (!user) return null;

  if (!canAccessHrPortal(user)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#061510] px-4">
        <div className="max-w-md rounded-xl border border-brand-200 bg-white p-8 text-center">
          <h1 className="text-xl font-bold text-brand-900">Access denied</h1>
          <p className="mt-2 text-sm text-brand-300">
            Only HR and administrators can access the HR portal.
          </p>
        </div>
      </div>
    );
  }

  return (
    <AIAssistantProvider>
      <GlassPortalShell
        sidebar={
          <GlassSidebar
            title="HR Portal"
            subtitle="Recruitment"
            items={CORE_NAV_ITEMS}
            pathname={pathname}
            storageKey="hr-sidebar-collapsed"
          />
        }
      >
        <div className="flex h-full min-h-0 min-w-0 flex-1 flex-col">
          <AIAwareTopBar notificationVariant="hr" editProfileHref="/hr/profile" />
          <AIAssistantMain contentClassName="flex-1 min-h-0 overflow-y-auto p-6">
            {children}
          </AIAssistantMain>
        </div>
      </GlassPortalShell>
      <FloatingAIButton />
    </AIAssistantProvider>
  );
}

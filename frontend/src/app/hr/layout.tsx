"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { NotificationBell } from "@/components/NotificationBell";
import { UserMenu } from "@/components/UserMenu";
import { canAccessHrPortal } from "@/lib/roles";

const CORE_NAV_ITEMS = [
  { href: "/hr/dashboard", label: "Dashboard", enabled: true },
  { href: "/hr/employees", label: "Employees", enabled: true },
  { href: "/hr/departments", label: "Departments", enabled: true },
  { href: "/hr/positions", label: "Positions", enabled: true },
  { href: "/hr/organization", label: "Organization", enabled: true },
  { href: "/hr/jobs", label: "Job Offers", enabled: true },
  { href: "/hr/onboarding", label: "Onboarding", enabled: true },
  { href: "/hr/onboarding/templates", label: "Task catalogue", enabled: true },
  { href: "/hr/leave", label: "Leave", enabled: true },
  { href: "/hr/documents", label: "Documents", enabled: true },
];

const LATER_NAV_ITEMS = [
  { href: "#", label: "Training", enabled: false },
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
      <div className="min-h-screen flex items-center justify-center bg-brand-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!user) return null;

  if (!canAccessHrPortal(user)) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 bg-brand-50">
        <div className="bg-white rounded-xl border border-brand-200 p-8 max-w-md text-center">
          <h1 className="text-xl font-bold text-brand-900">Access denied</h1>
          <p className="mt-2 text-sm text-brand-300">
            Only HR and administrators can access the HR portal.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex bg-brand-50">
      <aside className="w-64 bg-white border-r border-brand-200 flex flex-col">
        <div className="px-6 py-5 border-b border-brand-200">
          <p className="text-lg font-bold text-brand-900">HR Portal</p>
          <p className="text-xs text-brand-300 mt-1">Recruitment workspace</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          <p className="px-3 pb-2 text-xs font-semibold text-brand-300 uppercase tracking-wide">
            Core HR
          </p>
          {CORE_NAV_ITEMS.map((item) => (
            <NavLink key={item.label} item={item} pathname={pathname} />
          ))}
          <p className="px-3 pt-5 pb-2 text-xs font-semibold text-brand-300 uppercase tracking-wide">
            Coming later
          </p>
          {LATER_NAV_ITEMS.map((item) => (
            <NavLink key={item.label} item={item} pathname={pathname} />
          ))}
        </nav>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white border-b border-brand-200">
          <div className="px-6 h-14 flex items-center justify-end gap-3">
            <NotificationBell variant="hr" />
            <UserMenu editProfileHref="/hr/profile" />
          </div>
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}

function NavLink({
  item,
  pathname,
}: {
  item: { href: string; label: string; enabled: boolean };
  pathname: string;
}) {
  const active =
    item.enabled &&
    (pathname === item.href ||
      (pathname.startsWith(`${item.href}/`) &&
        !(item.href === "/hr/onboarding" && pathname.startsWith("/hr/onboarding/templates"))));

  if (!item.enabled) {
    return (
      <span className="flex items-center justify-between px-3 py-2 rounded-lg text-sm text-brand-300 cursor-not-allowed">
        {item.label}
        <span className="text-[10px] uppercase tracking-wide">Soon</span>
      </span>
    );
  }

  return (
    <Link
      href={item.href}
      className={`block px-3 py-2 rounded-lg text-sm font-medium transition ${
        active
          ? "bg-brand-100 text-brand-900"
          : "text-brand-900 hover:bg-brand-100"
      }`}
    >
      {item.label}
    </Link>
  );
}

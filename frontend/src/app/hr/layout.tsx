"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { NotificationBell } from "@/components/NotificationBell";
import { UserMenu } from "@/components/UserMenu";
import { canAccessHrPortal } from "@/lib/roles";

const NAV_ITEMS = [
  { href: "/hr/dashboard", label: "Dashboard", enabled: true },
  { href: "/hr/employees", label: "Employees", enabled: true },
  { href: "/hr/departments", label: "Departments", enabled: true },
  { href: "/hr/positions", label: "Positions", enabled: true },
  { href: "/hr/organization", label: "Organization", enabled: true },
  { href: "/hr/jobs", label: "Job Offers", enabled: true },
  { href: "/hr/onboarding", label: "Onboarding", enabled: true },
  { href: "#", label: "Leave", enabled: false },
  { href: "#", label: "Training", enabled: false },
  { href: "#", label: "Documents", enabled: false },
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
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!user) return null;

  if (!canAccessHrPortal(user)) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="bg-white rounded-xl shadow-sm border p-8 max-w-md text-center">
          <h1 className="text-xl font-bold text-gray-900">Access denied</h1>
          <p className="mt-2 text-sm text-gray-600">
            Only HR and administrators can access the HR portal.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex bg-gray-50">
      <aside className="w-64 bg-white border-r flex flex-col">
        <div className="px-6 py-5 border-b">
          <p className="text-lg font-bold text-gray-900">HR Portal</p>
          <p className="text-xs text-gray-500 mt-1">Recruitment workspace</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          <p className="px-3 pb-2 text-xs font-semibold text-gray-400 uppercase tracking-wide">
            Core HR
          </p>
          {NAV_ITEMS.slice(0, 7).map((item) => (
            <NavLink key={item.label} item={item} pathname={pathname} />
          ))}
          <p className="px-3 pt-5 pb-2 text-xs font-semibold text-gray-400 uppercase tracking-wide">
            Coming later
          </p>
          {NAV_ITEMS.slice(7).map((item) => (
            <NavLink key={item.label} item={item} pathname={pathname} />
          ))}
        </nav>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white border-b border-gray-200">
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
  const active = item.enabled && (pathname === item.href || pathname.startsWith(`${item.href}/`));

  if (!item.enabled) {
    return (
      <span className="flex items-center justify-between px-3 py-2 rounded-lg text-sm text-gray-400 cursor-not-allowed">
        {item.label}
        <span className="text-[10px] uppercase tracking-wide">Soon</span>
      </span>
    );
  }

  return (
    <Link
      href={item.href}
      className={`block px-3 py-2 rounded-lg text-sm font-medium transition ${
        active ? "bg-brand-50 text-brand-700" : "text-gray-700 hover:bg-gray-50"
      }`}
    >
      {item.label}
    </Link>
  );
}

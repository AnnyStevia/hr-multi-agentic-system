"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { ChevronLeft, ChevronRight, type LucideIcon } from "lucide-react";

const EASE = "cubic-bezier(0.22, 1, 0.36, 1)";
const DURATION = "duration-500";

export type GlassNavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  enabled?: boolean;
  exact?: boolean;
  nested?: boolean;
  isActive?: (pathname: string) => boolean;
};

type GlassSidebarProps = {
  title: string;
  subtitle?: string;
  items: GlassNavItem[];
  pathname: string;
  storageKey?: string;
  footer?: ReactNode;
};

export function GlassSidebar({
  title,
  subtitle,
  items,
  pathname,
  storageKey = "portal-sidebar-collapsed",
  footer,
}: GlassSidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(storageKey);
      if (stored === "1") setCollapsed(true);
    } catch {
      /* ignore */
    }
    setReady(true);
  }, [storageKey]);

  const toggle = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(storageKey, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  return (
    <aside
      style={{ transitionTimingFunction: EASE }}
      className={`relative z-20 flex h-full shrink-0 flex-col overflow-hidden rounded-[2rem] border border-white/15 bg-white/[0.08] shadow-[0_8px_40px_-12px_rgba(0,0,0,0.45)] backdrop-blur-2xl will-change-[width] transition-[width,padding] ${DURATION} ${
        collapsed ? "w-[4.5rem]" : "w-[15.5rem]"
      } ${ready ? "opacity-100" : "opacity-0"}`}
      aria-label={`${title} navigation`}
    >
      <div
        style={{ transitionTimingFunction: EASE }}
        className={`flex shrink-0 items-center border-b border-white/10 transition-[padding,gap] ${DURATION} ${
          collapsed ? "justify-center gap-0 px-2 py-3.5" : "gap-2.5 px-3.5 py-4"
        }`}
      >
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-white/20 bg-white/10">
          <div className="grid grid-cols-2 gap-[3px]" aria-hidden="true">
            <span className="h-1.5 w-1.5 rounded-[2px] bg-white" />
            <span className="h-1.5 w-1.5 rounded-[2px] bg-white/65" />
            <span className="h-1.5 w-1.5 rounded-[2px] bg-white/65" />
            <span className="h-1.5 w-1.5 rounded-[2px] bg-white" />
          </div>
        </div>

        <div
          style={{ transitionTimingFunction: EASE }}
          className={`min-w-0 overflow-hidden transition-[max-width,opacity,transform,margin] ${DURATION} ${
            collapsed
              ? "max-w-0 -translate-x-2 opacity-0"
              : "max-w-[9.5rem] translate-x-0 opacity-100"
          }`}
        >
          <p className="truncate whitespace-nowrap text-[13px] font-semibold tracking-wide text-white">
            {title}
          </p>
          {subtitle ? (
            <p className="mt-0.5 truncate whitespace-nowrap text-[10px] font-medium uppercase tracking-[0.14em] text-white/45">
              {subtitle}
            </p>
          ) : null}
        </div>
      </div>

      <nav
        style={{ transitionTimingFunction: EASE }}
        className={`flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto overflow-x-hidden py-3 transition-[padding] ${DURATION} ${
          collapsed ? "px-2" : "px-2.5"
        }`}
      >
        {items.map((item) => (
          <GlassNavLink
            key={`${item.href}-${item.label}`}
            item={item}
            pathname={pathname}
            collapsed={collapsed}
          />
        ))}
      </nav>

      <div
        style={{ transitionTimingFunction: EASE }}
        className={`flex shrink-0 items-center border-t border-white/10 transition-[padding,justify-content] ${DURATION} ${
          collapsed ? "justify-center px-2 py-3" : "justify-between px-3 py-3"
        }`}
      >
        {footer ? (
          <div
            style={{ transitionTimingFunction: EASE }}
            className={`min-w-0 overflow-hidden transition-[max-width,opacity] ${DURATION} ${
              collapsed ? "max-w-0 opacity-0" : "max-w-full opacity-100"
            }`}
          >
            {footer}
          </div>
        ) : (
          <span aria-hidden className="hidden" />
        )}
        <button
          type="button"
          onClick={toggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/15 bg-white/10 text-white/80 transition-colors duration-300 hover:bg-white/20 hover:text-white"
        >
          <span className="relative flex h-4 w-4 items-center justify-center">
            <ChevronLeft
              style={{ transitionTimingFunction: EASE }}
              className={`absolute h-4 w-4 transition-all ${DURATION} ${
                collapsed
                  ? "rotate-180 opacity-0 scale-75"
                  : "rotate-0 opacity-100 scale-100"
              }`}
              strokeWidth={2}
            />
            <ChevronRight
              style={{ transitionTimingFunction: EASE }}
              className={`absolute h-4 w-4 transition-all ${DURATION} ${
                collapsed
                  ? "rotate-0 opacity-100 scale-100"
                  : "-rotate-180 opacity-0 scale-75"
              }`}
              strokeWidth={2}
            />
          </span>
        </button>
      </div>
    </aside>
  );
}

function GlassNavLink({
  item,
  pathname,
  collapsed,
}: {
  item: GlassNavItem;
  pathname: string;
  collapsed: boolean;
}) {
  const enabled = item.enabled !== false;
  const Icon = item.icon;
  const active = enabled
    ? item.isActive
      ? item.isActive(pathname)
      : item.exact
        ? pathname === item.href
        : pathname === item.href || pathname.startsWith(`${item.href}/`)
    : false;

  const shell = `group relative flex h-11 w-full items-center overflow-hidden rounded-full text-sm font-medium transition-[padding,gap,background-color,color,box-shadow] ${DURATION}`;
  const sizing = collapsed
    ? "justify-center gap-0 px-0"
    : `justify-start gap-3 px-3 ${item.nested ? "pl-5" : ""}`;

  const labelClass = `overflow-hidden whitespace-nowrap transition-[max-width,opacity,transform,margin] ${DURATION} ${
    collapsed
      ? "max-w-0 translate-x-[-8px] opacity-0"
      : "max-w-[11rem] translate-x-0 opacity-100"
  }`;

  if (!enabled) {
    return (
      <span
        style={{ transitionTimingFunction: EASE }}
        className={`${shell} ${sizing} cursor-not-allowed text-white/30`}
        title={collapsed ? `${item.label} (Soon)` : undefined}
      >
        <Icon className="h-[18px] w-[18px] shrink-0" strokeWidth={1.75} />
        <span style={{ transitionTimingFunction: EASE }} className={labelClass}>
          {item.label}
        </span>
      </span>
    );
  }

  return (
    <Link
      href={item.href}
      title={collapsed ? item.label : undefined}
      style={{ transitionTimingFunction: EASE }}
      className={`${shell} ${sizing} ${
        active
          ? "bg-white text-[#0b1f18] shadow-[0_4px_18px_-6px_rgba(255,255,255,0.55)]"
          : "text-white/75 hover:bg-white/10 hover:text-white"
      }`}
    >
      <Icon
        className={`h-[18px] w-[18px] shrink-0 transition-colors duration-300 ${
          active ? "text-[#0b1f18]" : "text-white/80 group-hover:text-white"
        }`}
        strokeWidth={active ? 2.1 : 1.75}
      />
      <span style={{ transitionTimingFunction: EASE }} className={labelClass}>
        {item.label}
      </span>
    </Link>
  );
}

/** Dark forest shell that frames the floating glass rail + content stage. */
export function GlassPortalShell({
  sidebar,
  children,
}: {
  sidebar: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="relative flex h-screen overflow-hidden bg-[#061510] p-3">
      <div
        className="pointer-events-none absolute inset-0"
        aria-hidden="true"
        style={{
          background:
            "radial-gradient(ellipse 70% 55% at 12% 20%, rgba(2,152,112,0.28), transparent 55%), radial-gradient(ellipse 50% 40% at 85% 80%, rgba(15,34,74,0.35), transparent 50%), linear-gradient(160deg, #0a2218 0%, #061510 45%, #040c0a 100%)",
        }}
      />
      <div className="relative z-10 flex h-full min-h-0 w-full gap-3">
        {sidebar}
        <div
          className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-[1.75rem] bg-[#f4f7f6] shadow-[0_12px_40px_-16px_rgba(0,0,0,0.5)] transition-[flex-basis] duration-500"
          style={{ transitionTimingFunction: EASE }}
        >
          {children}
        </div>
      </div>
    </div>
  );
}

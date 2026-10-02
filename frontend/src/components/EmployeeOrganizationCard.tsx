"use client";

import type { EmployeeOrganization } from "@/types/organization";
import { cn } from "@/lib/utils";

export function EmployeeOrganizationCard({
  organization,
  title = "Organization",
}: {
  organization: EmployeeOrganization;
  title?: string;
}) {
  const name = organization.employee.full_name;
  const position =
    organization.position?.title || organization.employee.position || "—";
  const department =
    organization.department?.name || organization.employee.department || "—";

  return (
    <div className="rounded-2xl border border-brand-200/70 bg-white p-5 shadow-[0_8px_24px_-18px_rgba(15,34,74,0.35)]">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-brand-300">
        {title}
      </p>

      <div className="mt-3 flex items-center gap-3">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-[#0f224a] text-sm font-semibold text-white shadow-sm">
          {initials(name)}
        </span>
        <div className="min-w-0">
          <p className="truncate text-base font-semibold text-brand-900">{name}</p>
          <p className="truncate text-[13px] text-brand-600">{position}</p>
        </div>
      </div>

      <dl className="mt-4 space-y-3">
        <Detail label="Department" value={department} />
        <Detail
          label="Reports to"
          value={
            organization.manager
              ? `${organization.manager.full_name}${
                  organization.manager.position
                    ? ` · ${organization.manager.position}`
                    : ""
                }`
              : "—"
          }
        />
      </dl>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className={cn("rounded-xl bg-[#f7faf9] px-3 py-2.5")}>
      <dt className="text-[10px] font-semibold uppercase tracking-[0.12em] text-brand-300">
        {label}
      </dt>
      <dd className="mt-0.5 text-sm font-medium text-brand-900">{value}</dd>
    </div>
  );
}

function initials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

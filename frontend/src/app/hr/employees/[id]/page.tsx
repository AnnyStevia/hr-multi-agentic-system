"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ArrowLeft,
  Briefcase,
  Building2,
  Cake,
  CalendarDays,
  Clock3,
  FileText,
  GraduationCap,
  LayoutDashboard,
  Mail,
  MapPin,
  Network,
  Palmtree,
  Phone,
  Star,
  UserRound,
} from "lucide-react";
import { DocumentsSection } from "@/components/DocumentsSection";
import { EmployeeStatusBadge } from "@/components/EmployeeStatusBadge";
import { api } from "@/lib/api";
import { addCalendarDays, formatDisplayDate } from "@/components/calendar/dateUtils";
import { EMPLOYMENT_TYPE_LABELS, type Employee } from "@/types/employees";
import type { LeaveBalance } from "@/types/leave";
import type { EmployeeOrganization } from "@/types/organization";
import type {
  EmployeeEducation,
  EmployeeExperience,
  EmployeeProfile,
} from "@/types/profile";
import { cn } from "@/lib/utils";

const card =
  "rounded-2xl border border-brand-200/70 bg-white shadow-[0_8px_24px_-18px_rgba(15,34,74,0.35)]";

type TabId =
  | "overview"
  | "personal"
  | "employment"
  | "leave"
  | "education"
  | "experience"
  | "documents"
  | "training"
  | "evaluations";

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function relativeFrom(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return null;
  const days = Math.round((Date.now() - date.getTime()) / (24 * 60 * 60 * 1000));
  if (days < 0) return "upcoming";
  if (days === 0) return "today";
  if (days < 7) return `${days} day${days === 1 ? "" : "s"} ago`;
  if (days < 45) {
    const weeks = Math.max(1, Math.round(days / 7));
    return `${weeks} week${weeks === 1 ? "" : "s"} ago`;
  }
  if (days < 365) {
    const months = Math.max(1, Math.round(days / 30));
    return `${months} month${months === 1 ? "" : "s"} ago`;
  }
  const years = Math.max(1, Math.round(days / 365));
  return `${years} year${years === 1 ? "" : "s"} ago`;
}

function ageFromDob(value: string | null | undefined): number | null {
  if (!value) return null;
  const dob = new Date(`${value}T00:00:00`);
  if (Number.isNaN(dob.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - dob.getFullYear();
  const m = now.getMonth() - dob.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < dob.getDate())) age -= 1;
  return age >= 0 ? age : null;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function leaveBarColor(used: number, allowed: number): string {
  if (allowed <= 0) return "bg-brand-200";
  const ratio = used / allowed;
  if (ratio >= 0.85) return "bg-rose-500";
  if (ratio >= 0.5) return "bg-amber-500";
  return "bg-emerald-500";
}

export default function EmployeeProfilePage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const employeeId = Number(params.id);
  const [employee, setEmployee] = useState<Employee | null>(null);
  const [organization, setOrganization] = useState<EmployeeOrganization | null>(
    null
  );
  const [profile, setProfile] = useState<EmployeeProfile | null>(null);
  const [educations, setEducations] = useState<EmployeeEducation[]>([]);
  const [experiences, setExperiences] = useState<EmployeeExperience[]>([]);
  const [balances, setBalances] = useState<LeaveBalance[]>([]);
  const [pictureUrl, setPictureUrl] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [deactivating, setDeactivating] = useState(false);
  const [converting, setConverting] = useState(false);
  const [tab, setTab] = useState<TabId>("overview");

  useEffect(() => {
    const load = async () => {
      setError("");
      setLoading(true);
      try {
        const [emp, org, profileData, eduData, expData, leaveData] =
          await Promise.all([
            api.getEmployee(employeeId),
            api.getEmployeeOrganization(employeeId),
            api.getEmployeeProfile(employeeId).catch(() => null),
            api.listEmployeeEducation(employeeId).catch(() => []),
            api.listEmployeeExperience(employeeId).catch(() => []),
            api.listEmployeeLeaveBalances(employeeId).catch(() => []),
          ]);
        setEmployee(emp);
        setOrganization(org);
        setProfile(profileData);
        setEducations(eduData);
        setExperiences(expData);
        setBalances(leaveData);

        const hasPicture =
          Boolean(profileData?.has_profile_picture) ||
          Boolean(emp.has_profile_picture);
        if (hasPicture) {
          try {
            const pic = await api.getEmployeeProfilePictureUrl(employeeId);
            setPictureUrl(pic.url);
          } catch {
            setPictureUrl(emp.profile_picture_url ?? null);
          }
        } else {
          setPictureUrl(null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load employee");
      } finally {
        setLoading(false);
      }
    };
    if (!Number.isNaN(employeeId)) void load();
  }, [employeeId]);

  const handleDeactivate = async () => {
    if (!employee || employee.employment_status === "inactive") return;
    setDeactivating(true);
    setError("");
    try {
      setEmployee(await api.deactivateEmployee(employee.id));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to deactivate employee"
      );
    } finally {
      setDeactivating(false);
    }
  };

  const handleConvert = async () => {
    if (!employee || employee.employment_type !== "internship") return;
    if (
      !window.confirm(
        "Convert this intern to a full-time employee? The employment end date will be cleared."
      )
    ) {
      return;
    }
    setConverting(true);
    setError("");
    try {
      setEmployee(await api.convertInternToEmployee(employee.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to convert intern");
    } finally {
      setConverting(false);
    }
  };

  const age = ageFromDob(profile?.date_of_birth);
  const hireRelative = relativeFrom(employee?.hire_date);
  const locationLine = [profile?.city, profile?.country].filter(Boolean).join(", ");
  const leaveYear = balances[0]?.year ?? new Date().getFullYear();
  const managerName =
    organization?.manager?.full_name ||
    (employee?.manager_id ? `Employee #${employee.manager_id}` : "—");

  const tabs: Array<{ id: TabId; label: string; icon: ReactNode }> = useMemo(
    () => [
      { id: "overview", label: "Overview", icon: <LayoutDashboard className="size-3.5" /> },
      { id: "personal", label: "Personal", icon: <UserRound className="size-3.5" /> },
      { id: "employment", label: "Employment", icon: <Briefcase className="size-3.5" /> },
      { id: "leave", label: "Leave", icon: <Palmtree className="size-3.5" /> },
      { id: "education", label: "Education", icon: <GraduationCap className="size-3.5" /> },
      { id: "experience", label: "Experience", icon: <Network className="size-3.5" /> },
      { id: "documents", label: "Documents", icon: <FileText className="size-3.5" /> },
      { id: "training", label: "Training", icon: <Star className="size-3.5" /> },
      { id: "evaluations", label: "Evaluations", icon: <Clock3 className="size-3.5" /> },
    ],
    []
  );

  if (loading) {
    return (
      <div className="-m-6 flex min-h-[50vh] items-center justify-center bg-[#f3f6f5] p-6">
        <div className="h-7 w-7 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
      </div>
    );
  }

  if (!employee) {
    return (
      <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 sm:p-6">
        <p className="text-sm text-red-700">{error || "Employee not found"}</p>
        <button
          type="button"
          onClick={() => router.push("/hr/employees")}
          className="mt-4 text-sm font-medium text-brand-700"
        >
          Back to employees
        </button>
      </div>
    );
  }

  return (
    <div className="-m-6 min-h-full bg-[#f3f6f5] p-5 pb-8 sm:p-6">
      <div className="mx-auto max-w-[1200px] space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <Link
            href="/hr/employees"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-[#0f224a]/70 transition hover:text-[#0f224a]"
          >
            <ArrowLeft className="size-4" />
            Back to employees
          </Link>
          <div className="flex flex-wrap gap-2">
            <Link
              href={`/hr/employees/${employee.id}/edit`}
              className="inline-flex h-10 items-center rounded-xl border border-brand-200 bg-white px-4 text-sm font-semibold text-brand-700 transition hover:bg-[#f7faf9]"
            >
              Edit
            </Link>
            {employee.employment_type === "internship" ? (
              <button
                type="button"
                disabled={converting}
                onClick={() => void handleConvert()}
                className="inline-flex h-10 items-center rounded-xl border border-brand-200 bg-white px-4 text-sm font-semibold text-brand-700 transition hover:bg-brand-50 disabled:opacity-50"
              >
                {converting ? "Converting…" : "Convert to employee"}
              </button>
            ) : null}
            {employee.employment_status !== "inactive" ? (
              <button
                type="button"
                disabled={deactivating}
                onClick={() => void handleDeactivate()}
                className="inline-flex h-10 items-center rounded-xl border border-rose-200 bg-white px-4 text-sm font-semibold text-rose-700 transition hover:bg-rose-50 disabled:opacity-50"
              >
                {deactivating ? "Deactivating…" : "Deactivate"}
              </button>
            ) : null}
          </div>
        </div>

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {/* Profile summary */}
        <section className={cn(card, "p-5 sm:p-6")}>
          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
            <div className="flex min-w-0 items-start gap-4">
              {pictureUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={pictureUrl}
                  alt={employee.full_name}
                  className="h-[72px] w-[72px] rounded-full object-cover ring-2 ring-brand-100"
                />
              ) : (
                <span className="flex h-[72px] w-[72px] shrink-0 items-center justify-center rounded-full bg-[#0f224a] text-lg font-semibold text-white">
                  {initials(employee.full_name)}
                </span>
              )}
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-2xl font-semibold tracking-tight text-brand-900">
                    {employee.full_name}
                  </h1>
                  <EmployeeStatusBadge status={employee.employment_status} />
                </div>
                <p className="mt-1 text-[13px] text-brand-300">
                  {employee.employee_number}
                </p>
              </div>
            </div>

            <div className="grid min-w-0 flex-1 grid-cols-1 gap-4 sm:grid-cols-2 xl:max-w-3xl">
              <div className="space-y-2.5">
                <MetaLine
                  icon={<Briefcase className="size-3.5" />}
                  text={employee.position || "—"}
                />
                <MetaLine
                  icon={<Network className="size-3.5" />}
                  text={employee.department || "—"}
                />
                <MetaLine
                  icon={<MapPin className="size-3.5" />}
                  text={locationLine || "—"}
                />
              </div>
              <div className="space-y-2.5">
                <MetaLine
                  icon={<Mail className="size-3.5" />}
                  text={employee.email}
                />
                <MetaLine
                  icon={<Phone className="size-3.5" />}
                  text={employee.phone || "—"}
                />
                <MetaLine
                  icon={<Cake className="size-3.5" />}
                  text={
                    profile?.date_of_birth
                      ? `${formatDate(profile.date_of_birth)}${
                          age != null ? ` (${age} years old)` : ""
                        }`
                      : "—"
                  }
                />
              </div>
            </div>
          </div>
        </section>

        {/* Tabs */}
        <div className={cn(card, "overflow-hidden")}>
          <div className="flex gap-1 overflow-x-auto border-b border-brand-200/70 px-2">
            {tabs.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setTab(item.id)}
                className={cn(
                  "inline-flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-3 text-sm font-semibold transition",
                  tab === item.id
                    ? "border-brand-600 text-brand-700"
                    : "border-transparent text-brand-300 hover:text-brand-700"
                )}
              >
                {item.icon}
                {item.label}
              </button>
            ))}
          </div>

          <div className="space-y-5 p-5 sm:p-6">
            {tab === "overview" ? (
              <>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <QuickCard
                    label="Position"
                    value={employee.position || "—"}
                    meta={
                      EMPLOYMENT_TYPE_LABELS[employee.employment_type] ||
                      employee.employment_type
                    }
                    icon={<Briefcase className="size-4" />}
                    tone="bg-emerald-50 text-emerald-700"
                  />
                  <QuickCard
                    label="Department"
                    value={employee.department || "—"}
                    icon={<Building2 className="size-4" />}
                    tone="bg-sky-50 text-sky-700"
                  />
                  <QuickCard
                    label="Hire date"
                    value={formatDate(employee.hire_date)}
                    meta={hireRelative}
                    icon={<CalendarDays className="size-4" />}
                    tone="bg-teal-50 text-teal-700"
                  />
                  <QuickCard
                    label="Status"
                    valueNode={
                      <EmployeeStatusBadge status={employee.employment_status} />
                    }
                    icon={<UserRound className="size-4" />}
                    tone="bg-violet-50 text-violet-700"
                  />
                </div>

                {employee.current_work_status === "ON_LEAVE" &&
                employee.current_leave ? (
                  <LeaveStatusCard
                    leave={employee.current_leave}
                    onView={() => setTab("leave")}
                  />
                ) : null}

                <LeaveBalancesBlock
                  balances={balances}
                  year={leaveYear}
                  onViewHistory={() => setTab("leave")}
                />

                <InfoPanel
                  title="Personal information"
                  actionHref={`/hr/employees/${employee.id}/edit`}
                  actionLabel="Edit"
                >
                  <InfoGrid
                    items={[
                      { label: "Full name", value: employee.full_name },
                      {
                        label: "Address",
                        value: profile?.address || "—",
                      },
                      { label: "Email", value: employee.email },
                      { label: "City", value: profile?.city || "—" },
                      { label: "Phone", value: employee.phone || "—" },
                      { label: "Country", value: profile?.country || "—" },
                      {
                        label: "Date of birth",
                        value: formatDate(profile?.date_of_birth),
                      },
                      { label: "Nationality", value: "—" },
                    ]}
                  />
                </InfoPanel>

                <InfoPanel
                  title="Employment information"
                  actionHref={`/hr/employees/${employee.id}/edit`}
                  actionLabel="Edit"
                >
                  <InfoGrid
                    items={[
                      {
                        label: "Employee number",
                        value: employee.employee_number,
                      },
                      {
                        label: "Employment type",
                        value:
                          EMPLOYMENT_TYPE_LABELS[employee.employment_type] ||
                          employee.employment_type,
                      },
                      { label: "Position", value: employee.position || "—" },
                      {
                        label: "Hire date",
                        value: formatDate(employee.hire_date),
                      },
                      {
                        label: "Department",
                        value: employee.department || "—",
                      },
                      { label: "Reports to", value: managerName },
                      {
                        label: "Status",
                        valueNode: (
                          <EmployeeStatusBadge
                            status={employee.employment_status}
                          />
                        ),
                      },
                      ...(employee.employment_type === "internship" &&
                      employee.employment_end_date
                        ? [
                            {
                              label: "Internship end",
                              value: formatDate(employee.employment_end_date),
                            },
                          ]
                        : []),
                    ]}
                  />
                </InfoPanel>

                <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                  <ListPanel
                    title="Education"
                    empty="No education records."
                    items={educations.map((item) => ({
                      key: String(item.id),
                      title: `${item.degree || "Degree"} · ${item.institution}`,
                      meta: [item.field_of_study, formatRange(item.start_date, item.end_date)]
                        .filter(Boolean)
                        .join(" · "),
                    }))}
                  />
                  <ListPanel
                    title="Experience"
                    empty="No experience records."
                    items={experiences.map((item) => ({
                      key: String(item.id),
                      title: `${item.position} · ${item.company}`,
                      meta: [
                        item.description,
                        formatRange(item.start_date, item.end_date),
                      ]
                        .filter(Boolean)
                        .join(" · "),
                    }))}
                  />
                </div>

                <div>
                  <DocumentsSection
                    mode="hr"
                    employeeId={employee.id}
                    allowDelete
                  />
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <ComingSoon title="Training" />
                  <ComingSoon title="Evaluations" />
                </div>
              </>
            ) : null}

            {tab === "personal" ? (
              <InfoPanel
                title="Personal information"
                actionHref={`/hr/employees/${employee.id}/edit`}
                actionLabel="Edit"
              >
                <InfoGrid
                  items={[
                    { label: "Full name", value: employee.full_name },
                    { label: "Email", value: employee.email },
                    { label: "Phone", value: employee.phone || "—" },
                    {
                      label: "Date of birth",
                      value: formatDate(profile?.date_of_birth),
                    },
                    { label: "Address", value: profile?.address || "—" },
                    { label: "City", value: profile?.city || "—" },
                    { label: "Country", value: profile?.country || "—" },
                    { label: "Nationality", value: "—" },
                  ]}
                />
              </InfoPanel>
            ) : null}

            {tab === "employment" ? (
              <InfoPanel
                title="Employment information"
                actionHref={`/hr/employees/${employee.id}/edit`}
                actionLabel="Edit"
              >
                <InfoGrid
                  items={[
                    {
                      label: "Employee number",
                      value: employee.employee_number,
                    },
                    { label: "Position", value: employee.position || "—" },
                    {
                      label: "Department",
                      value: employee.department || "—",
                    },
                    {
                      label: "Employment type",
                      value:
                        EMPLOYMENT_TYPE_LABELS[employee.employment_type] ||
                        employee.employment_type,
                    },
                    {
                      label: "Hire date",
                      value: formatDate(employee.hire_date),
                    },
                    { label: "Reports to", value: managerName },
                    {
                      label: "Status",
                      valueNode: (
                        <EmployeeStatusBadge
                          status={employee.employment_status}
                        />
                      ),
                    },
                  ]}
                />
              </InfoPanel>
            ) : null}

            {tab === "leave" ? (
              <div className="space-y-5">
                {employee.current_work_status === "ON_LEAVE" &&
                employee.current_leave ? (
                  <LeaveStatusCard leave={employee.current_leave} />
                ) : null}
                <LeaveBalancesBlock balances={balances} year={leaveYear} />
                <Link
                  href="/hr/leave"
                  className="inline-flex text-sm font-semibold text-brand-700 hover:text-brand-800"
                >
                  Open leave workspace
                </Link>
              </div>
            ) : null}

            {tab === "education" ? (
              <ListPanel
                title="Education"
                empty="No education records."
                items={educations.map((item) => ({
                  key: String(item.id),
                  title: `${item.degree || "Degree"} · ${item.institution}`,
                  meta: [item.field_of_study, formatRange(item.start_date, item.end_date)]
                    .filter(Boolean)
                    .join(" · "),
                  body: item.description || undefined,
                }))}
              />
            ) : null}

            {tab === "experience" ? (
              <ListPanel
                title="Experience"
                empty="No experience records."
                items={experiences.map((item) => ({
                  key: String(item.id),
                  title: `${item.position} · ${item.company}`,
                  meta: formatRange(item.start_date, item.end_date),
                  body: item.description || undefined,
                }))}
              />
            ) : null}

            {tab === "documents" ? (
              <DocumentsSection
                mode="hr"
                employeeId={employee.id}
                allowDelete
              />
            ) : null}

            {tab === "training" ? <ComingSoon title="Training" /> : null}
            {tab === "evaluations" ? <ComingSoon title="Evaluations" /> : null}
          </div>
        </div>
      </div>
    </div>
  );
}

function formatRange(start: string | null, end: string | null): string {
  const a = formatDate(start);
  const b = end ? formatDate(end) : "present";
  if (a === "—" && !end) return "—";
  return `${a} – ${b}`;
}

function MetaLine({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-2 text-[13px] text-brand-700">
      <span className="text-brand-300">{icon}</span>
      <span className="truncate">{text}</span>
    </div>
  );
}

function QuickCard({
  label,
  value,
  valueNode,
  meta,
  icon,
  tone,
}: {
  label: string;
  value?: string;
  valueNode?: ReactNode;
  meta?: string | null;
  icon: ReactNode;
  tone: string;
}) {
  return (
    <div className={cn(card, "p-4")}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
            {label}
          </p>
          <div className="mt-1.5 text-sm font-semibold text-brand-900">
            {valueNode ?? value}
          </div>
          {meta ? (
            <p className="mt-0.5 text-[12px] text-brand-300">{meta}</p>
          ) : null}
        </div>
        <span
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
            tone
          )}
        >
          {icon}
        </span>
      </div>
    </div>
  );
}

function LeaveStatusCard({
  leave,
  onView,
}: {
  leave: { leave_type: string; start_date: string; end_date: string };
  onView?: () => void;
}) {
  const returnsOn = addCalendarDays(leave.end_date, 1);
  return (
    <div className="rounded-2xl border border-emerald-200 bg-emerald-50/80 px-5 py-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-emerald-900">
            Currently on leave
          </p>
          <p className="mt-1 text-sm font-medium text-emerald-800">
            {leave.leave_type}
          </p>
          <p className="mt-1 text-[13px] text-emerald-800/80">
            {formatDisplayDate(leave.start_date)} →{" "}
            {formatDisplayDate(leave.end_date)}
          </p>
          <p className="mt-1 text-[13px] font-medium text-emerald-900">
            Returns {formatDisplayDate(returnsOn)}
          </p>
        </div>
        {onView ? (
          <button
            type="button"
            onClick={onView}
            className="inline-flex h-9 items-center justify-center rounded-xl border border-emerald-300 bg-white px-3 text-xs font-semibold text-emerald-800 transition hover:bg-emerald-50"
          >
            View leave details
          </button>
        ) : null}
      </div>
    </div>
  );
}

function LeaveBalancesBlock({
  balances,
  year,
  onViewHistory,
}: {
  balances: LeaveBalance[];
  year: number;
  onViewHistory?: () => void;
}) {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-brand-900">
          Leave balances ({year})
        </h2>
        {onViewHistory ? (
          <button
            type="button"
            onClick={onViewHistory}
            className="text-xs font-semibold text-brand-600 hover:text-brand-700"
          >
            View leave history
          </button>
        ) : null}
      </div>
      {balances.length === 0 ? (
        <div className={cn(card, "px-4 py-8 text-center text-sm text-brand-300")}>
          No leave policies for the current year.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {balances.map((balance) => {
            const allowed = balance.days_allowed || 0;
            const used = balance.days_used || 0;
            const pct = allowed > 0 ? Math.min(100, (used / allowed) * 100) : 0;
            return (
              <div
                key={`${balance.leave_type_id}-${balance.year}`}
                className={cn(card, "p-4")}
              >
                <p className="text-sm font-semibold text-brand-900">
                  {balance.leave_type_name}
                </p>
                <p className="mt-1 text-lg font-semibold tabular-nums text-brand-900">
                  {balance.days_available}{" "}
                  <span className="text-sm font-medium text-brand-300">
                    available
                  </span>
                </p>
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-brand-100">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      leaveBarColor(used, allowed)
                    )}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <p className="mt-2 text-[12px] text-brand-300">
                  {used} used of {allowed}
                  {balance.days_pending > 0
                    ? ` · ${balance.days_pending} pending`
                    : ""}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function InfoPanel({
  title,
  actionHref,
  actionLabel,
  children,
}: {
  title: string;
  actionHref?: string;
  actionLabel?: string;
  children: ReactNode;
}) {
  return (
    <section className={cn(card, "overflow-hidden")}>
      <div className="flex items-center justify-between gap-3 border-b border-brand-200/70 px-5 py-3.5">
        <h2 className="text-sm font-semibold text-brand-900">{title}</h2>
        {actionHref && actionLabel ? (
          <Link
            href={actionHref}
            className="text-xs font-semibold text-brand-600 hover:text-brand-700"
          >
            {actionLabel}
          </Link>
        ) : null}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function InfoGrid({
  items,
}: {
  items: Array<{
    label: string;
    value?: string;
    valueNode?: ReactNode;
  }>;
}) {
  return (
    <div className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
      {items.map((item) => (
        <div key={item.label}>
          <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-brand-300">
            {item.label}
          </p>
          <div className="mt-1 text-sm font-medium text-brand-900">
            {item.valueNode ?? item.value ?? "—"}
          </div>
        </div>
      ))}
    </div>
  );
}

function ListPanel({
  title,
  empty,
  items,
}: {
  title: string;
  empty: string;
  items: Array<{
    key: string;
    title: string;
    meta?: string;
    body?: string;
  }>;
}) {
  return (
    <section className={cn(card, "overflow-hidden")}>
      <div className="border-b border-brand-200/70 px-5 py-3.5">
        <h2 className="text-sm font-semibold text-brand-900">{title}</h2>
      </div>
      <div className="p-4">
        {items.length === 0 ? (
          <p className="px-1 py-6 text-center text-sm text-brand-300">{empty}</p>
        ) : (
          <ul className="space-y-2">
            {items.map((item) => (
              <li
                key={item.key}
                className="rounded-xl border border-brand-200/60 bg-[#f7faf9] px-4 py-3"
              >
                <p className="text-sm font-semibold text-brand-900">
                  {item.title}
                </p>
                {item.meta ? (
                  <p className="mt-0.5 text-[12px] text-brand-300">{item.meta}</p>
                ) : null}
                {item.body ? (
                  <p className="mt-1.5 text-[13px] text-brand-700/80">
                    {item.body}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function ComingSoon({ title }: { title: string }) {
  return (
    <div className={cn(card, "flex flex-col items-center justify-center px-4 py-10 text-center")}>
      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#f3f6f5] text-brand-300">
        <Clock3 className="size-4" />
      </span>
      <p className="mt-3 text-sm font-semibold text-brand-900">{title}</p>
      <p className="mt-1 text-[13px] text-brand-300">Coming later</p>
    </div>
  );
}

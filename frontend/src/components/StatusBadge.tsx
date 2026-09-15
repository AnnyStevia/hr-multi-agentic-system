import type { ApplicationStatus } from "@/types/applications";

const BADGE_STYLES: Record<ApplicationStatus, string> = {
  submitted: "bg-gray-100 text-gray-800",
  screening: "bg-amber-100 text-amber-800",
  shortlisted: "bg-blue-100 text-blue-800",
  rejected: "bg-red-100 text-red-800",
  hired: "bg-green-100 text-green-800",
};

const LABELS: Record<ApplicationStatus, string> = {
  submitted: "Submitted",
  screening: "Screening",
  shortlisted: "Shortlisted",
  rejected: "Rejected",
  hired: "Hired",
};

export function StatusBadge({ status }: { status: ApplicationStatus }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${BADGE_STYLES[status]}`}>
      {LABELS[status]}
    </span>
  );
}

export function statusLabel(status: ApplicationStatus): string {
  return LABELS[status];
}

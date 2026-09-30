import type { OffboardingClearanceStatus } from "@/types/offboarding";
import { OFFBOARDING_CLEARANCE_STATUS_LABELS } from "@/types/offboarding";

const BADGE_STYLES: Record<OffboardingClearanceStatus, string> = {
  pending: "bg-gray-100 text-gray-700",
  cleared: "bg-green-100 text-green-800",
  not_applicable: "bg-amber-100 text-amber-800",
};

export function OffboardingClearanceStatusBadge({
  status,
}: {
  status: OffboardingClearanceStatus;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${BADGE_STYLES[status]}`}
    >
      {OFFBOARDING_CLEARANCE_STATUS_LABELS[status]}
    </span>
  );
}

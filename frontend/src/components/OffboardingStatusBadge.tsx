import type { OffboardingStatus } from "@/types/offboarding";
import { OFFBOARDING_STATUS_LABELS } from "@/types/offboarding";

const BADGE_STYLES: Record<OffboardingStatus, string> = {
  initiated: "bg-amber-100 text-amber-800",
  in_progress: "bg-blue-100 text-blue-800",
  pending_clearance: "bg-orange-100 text-orange-800",
  completed: "bg-green-100 text-green-800",
  cancelled: "bg-gray-100 text-gray-700",
};

export function OffboardingStatusBadge({ status }: { status: OffboardingStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${BADGE_STYLES[status]}`}
    >
      {OFFBOARDING_STATUS_LABELS[status]}
    </span>
  );
}

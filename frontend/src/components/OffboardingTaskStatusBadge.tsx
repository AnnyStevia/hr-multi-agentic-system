import type { OffboardingTaskStatus } from "@/types/offboarding";
import { OFFBOARDING_TASK_STATUS_LABELS } from "@/types/offboarding";

const BADGE_STYLES: Record<OffboardingTaskStatus, string> = {
  pending: "bg-gray-100 text-gray-700",
  in_progress: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  skipped: "bg-amber-100 text-amber-800",
};

export function OffboardingTaskStatusBadge({ status }: { status: OffboardingTaskStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${BADGE_STYLES[status]}`}
    >
      {OFFBOARDING_TASK_STATUS_LABELS[status]}
    </span>
  );
}

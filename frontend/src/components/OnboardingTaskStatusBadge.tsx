import type { OnboardingTaskStatus } from "@/types/onboarding";

const BADGE_STYLES: Record<OnboardingTaskStatus, string> = {
  pending: "bg-amber-100 text-amber-800",
  completed: "bg-green-100 text-green-800",
};

const LABELS: Record<OnboardingTaskStatus, string> = {
  pending: "Pending",
  completed: "Completed",
};

export function OnboardingTaskStatusBadge({ status }: { status: OnboardingTaskStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${BADGE_STYLES[status]}`}
    >
      {LABELS[status]}
    </span>
  );
}

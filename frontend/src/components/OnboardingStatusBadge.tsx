import type { OnboardingStatus } from "@/types/onboarding";

const BADGE_STYLES: Record<OnboardingStatus, string> = {
  in_progress: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
};

const LABELS: Record<OnboardingStatus, string> = {
  in_progress: "In progress",
  completed: "Completed",
};

export function OnboardingStatusBadge({ status }: { status: OnboardingStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${BADGE_STYLES[status]}`}
    >
      {LABELS[status]}
    </span>
  );
}

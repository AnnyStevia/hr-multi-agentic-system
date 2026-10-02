import type { OnboardingTaskStatus } from "@/types/onboarding";

const BADGE_STYLES: Record<OnboardingTaskStatus, string> = {
  pending:
    "bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-600/15",
  completed:
    "bg-emerald-50 text-emerald-800 ring-1 ring-inset ring-emerald-600/15",
};

const LABELS: Record<OnboardingTaskStatus, string> = {
  pending: "Pending",
  completed: "Completed",
};

export function OnboardingTaskStatusBadge({
  status,
}: {
  status: OnboardingTaskStatus;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold ${BADGE_STYLES[status]}`}
    >
      {LABELS[status]}
    </span>
  );
}

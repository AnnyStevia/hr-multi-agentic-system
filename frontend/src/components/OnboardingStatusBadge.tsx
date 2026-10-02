import type { OnboardingStatus } from "@/types/onboarding";

const BADGE_STYLES: Record<OnboardingStatus, string> = {
  in_progress:
    "bg-sky-50 text-sky-800 ring-1 ring-inset ring-sky-600/15",
  completed:
    "bg-emerald-50 text-emerald-800 ring-1 ring-inset ring-emerald-600/15",
};

const LABELS: Record<OnboardingStatus, string> = {
  in_progress: "In progress",
  completed: "Completed",
};

export function OnboardingStatusBadge({ status }: { status: OnboardingStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold ${BADGE_STYLES[status]}`}
    >
      {LABELS[status]}
    </span>
  );
}

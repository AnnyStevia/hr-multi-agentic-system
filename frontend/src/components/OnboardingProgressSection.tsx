"use client";

import { ApplicationSection } from "@/components/ApplicationSection";
import { OnboardingStatusBadge } from "@/components/OnboardingStatusBadge";
import type { OnboardingProgress } from "@/types/onboarding";

type OnboardingProgressSectionProps = {
  progress: OnboardingProgress | null;
  loading?: boolean;
};

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function OnboardingProgressSection({
  progress,
  loading = false,
}: OnboardingProgressSectionProps) {
  if (loading && !progress) {
    return (
      <ApplicationSection title="Onboarding Progress">
        <div className="py-8 flex justify-center">
          <div className="animate-spin rounded-full h-7 w-7 border-b-2 border-brand-600" />
        </div>
      </ApplicationSection>
    );
  }

  if (!progress) {
    return null;
  }

  return (
    <ApplicationSection title="Onboarding Progress">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-3xl font-bold text-gray-900">{progress.overall_percentage}%</p>
            <p className="mt-1 text-sm text-gray-600">Overall completion</p>
          </div>
          <div className="text-right space-y-1">
            <OnboardingStatusBadge status={progress.status} />
            {progress.completed_at && (
              <p className="text-xs text-gray-500">
                Completed {formatDateTime(progress.completed_at)}
              </p>
            )}
          </div>
        </div>

        <div className="h-2.5 w-full rounded-full bg-gray-100 overflow-hidden">
          <div
            className="h-full rounded-full bg-brand-600 transition-all"
            style={{ width: `${Math.min(100, Math.max(0, progress.overall_percentage))}%` }}
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-xs text-gray-500">Required tasks</p>
            <p className="mt-0.5 font-medium text-gray-900">
              {progress.required_tasks?.completed ?? progress.tasks.completed} /{" "}
              {progress.required_tasks?.total ?? progress.tasks.total}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Optional tasks</p>
            <p className="mt-0.5 font-medium text-gray-900">
              {progress.optional_tasks?.completed ?? 0} / {progress.optional_tasks?.total ?? 0}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Trainings</p>
            <p className="mt-0.5 font-medium text-gray-900">
              {progress.trainings.completed} / {progress.trainings.total}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Documents</p>
            <p className="mt-0.5 font-medium text-gray-900">{progress.documents.total}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">All tasks</p>
            <p className="mt-0.5 font-medium text-gray-900">
              {progress.tasks.completed} / {progress.tasks.total}
            </p>
          </div>
        </div>
      </div>
    </ApplicationSection>
  );
}

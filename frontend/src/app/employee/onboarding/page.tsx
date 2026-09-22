"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApplicationSection } from "@/components/ApplicationSection";
import { DocumentsSection } from "@/components/DocumentsSection";
import { OnboardingProgressSection } from "@/components/OnboardingProgressSection";
import { TrainingSection } from "@/components/TrainingSection";
import { OnboardingStatusBadge } from "@/components/OnboardingStatusBadge";
import { OnboardingTaskStatusBadge } from "@/components/OnboardingTaskStatusBadge";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import type { Onboarding, OnboardingProgress, OnboardingTask, OnboardingTaskType } from "@/types/onboarding";
import { ONBOARDING_TASK_TYPE_LABELS } from "@/types/onboarding";

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString();
}

const PROFILE_TYPES = new Set<OnboardingTaskType>([
  "profile_personal_info",
  "profile_picture",
  "education",
  "experience",
]);

function taskAction(
  task: OnboardingTask,
): { href?: string; sectionId?: string; label: string } | null {
  if (task.status !== "pending") return null;
  if (PROFILE_TYPES.has(task.task_type)) {
    return { href: "/employee/profile", label: "Go to profile" };
  }
  if (task.task_type === "document") {
    return { sectionId: "documents", label: "Upload document" };
  }
  if (task.task_type === "training") {
    return { sectionId: "trainings", label: "Complete training" };
  }
  if (task.task_type === "acknowledgement") {
    return { label: "Acknowledge" };
  }
  if (task.task_type === "manual") {
    return null;
  }
  return null;
}

export default function EmployeeOnboardingPage() {
  const { user, refreshUser } = useAuth();
  const [onboarding, setOnboarding] = useState<Onboarding | null>(null);
  const [progress, setProgress] = useState<OnboardingProgress | null>(null);
  const [tasks, setTasks] = useState<OnboardingTask[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<number | null>(null);

  const load = useCallback(async (opts?: { silent?: boolean }) => {
    const silent = opts?.silent ?? false;
    setError("");
    // Avoid full-page loading on refresh — focus/file-picker events would unmount
    // DocumentsSection and wipe an in-progress upload.
    if (!silent) setLoading(true);
    try {
      const [onboardingData, progressData, taskData] = await Promise.all([
        api.getMyOnboarding(),
        api.getMyOnboardingProgress(),
        api.listMyOnboardingTasks(),
      ]);
      setOnboarding(onboardingData);
      setProgress(progressData);
      setTasks(taskData);
      if (onboardingData.status === "completed") {
        await refreshUser();
      }
    } catch (err) {
      if (!silent) {
        setOnboarding(null);
        setProgress(null);
        setTasks([]);
      }
      setError(err instanceof Error ? err.message : "Failed to load onboarding");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [refreshUser]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        void load({ silent: true });
      }
    };
    // Do not listen to window "focus" — opening a file picker blurs/focuses the
    // window and would remount the upload form before submit.
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [load]);

  const handleAcknowledge = async (taskId: number) => {
    setActingId(taskId);
    setError("");
    try {
      await api.acknowledgeMyOnboardingTask(taskId);
      await load({ silent: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to acknowledge task");
    } finally {
      setActingId(null);
    }
  };

  const scrollToSection = (sectionId: string) => {
    document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  if (loading) {
    return (
      <div className="py-16 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" />
      </div>
    );
  }

  if (!onboarding) {
    return (
      <div className="flex justify-center px-4 py-16">
        <div className="bg-white rounded-xl shadow-sm border p-8 max-w-md w-full text-center">
          <h1 className="text-xl font-bold text-gray-900">Onboarding unavailable</h1>
          <p className="mt-2 text-sm text-gray-600">
            {error || "We could not find an onboarding record for your account."}
          </p>
          <button
            type="button"
            onClick={() => load()}
            className="mt-4 text-sm font-medium text-brand-700 hover:text-brand-800"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  const isComplete = onboarding.status === "completed";
  const pendingCount = tasks.filter((task) => task.status === "pending").length;
  const preferredDocumentType =
    tasks.find((task) => task.task_type === "document" && task.status === "pending" && task.document_type)
      ?.document_type ?? "id_document";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Welcome{user?.full_name ? `, ${user.full_name}` : ""}
        </h1>
        <p className="mt-1 text-sm text-gray-600">
          {isComplete
            ? "Your onboarding is complete. You can review your tasks below."
            : "Complete the linked actions below. Required tasks unlock full employee access when finished."}
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {isComplete && (
        <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded-lg text-sm">
          Onboarding complete. You now have full access to the employee portal.
        </div>
      )}

      <OnboardingProgressSection progress={progress} />

      <ApplicationSection title="Onboarding status">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-xs text-gray-500">Status</p>
            <div className="mt-1">
              <OnboardingStatusBadge status={onboarding.status} />
            </div>
          </div>
          <div>
            <p className="text-xs text-gray-500">Started</p>
            <p className="mt-0.5 text-gray-900">{formatDateTime(onboarding.started_at)}</p>
          </div>
          {onboarding.completed_at && (
            <div>
              <p className="text-xs text-gray-500">Completed</p>
              <p className="mt-0.5 text-gray-900">{formatDateTime(onboarding.completed_at)}</p>
            </div>
          )}
        </div>
      </ApplicationSection>

      <ApplicationSection title="Your tasks">
        {tasks.length === 0 ? (
          <p className="text-sm text-gray-500">
            No onboarding tasks have been assigned yet. Check back later or contact HR.
          </p>
        ) : (
          <>
            {!isComplete && (
              <p className="mb-4 text-sm text-gray-600">
                {pendingCount === 0
                  ? "All assigned tasks are done. Onboarding will complete automatically."
                  : `${pendingCount} pending task${pendingCount === 1 ? "" : "s"} remaining.`}
              </p>
            )}
            <div className="space-y-4">
              {tasks.map((task) => {
                const action = taskAction(task);
                return (
                  <div
                    key={task.id}
                    className={`border rounded-lg p-4 space-y-3 ${
                      task.status === "completed"
                        ? "border-green-100 bg-green-50/40"
                        : "border-gray-200 bg-white"
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-gray-900">{task.title}</p>
                        <p className="mt-1 text-xs text-gray-500">
                          {task.is_required ? "Required" : "Optional"}
                          {" · "}
                          {ONBOARDING_TASK_TYPE_LABELS[task.task_type] || task.task_type}
                        </p>
                        {task.description && (
                          <p className="mt-1 text-sm text-gray-600">{task.description}</p>
                        )}
                        {task.task_type === "manual" && task.status === "pending" && (
                          <p className="mt-1 text-xs text-gray-500">Waiting for HR to complete this task.</p>
                        )}
                      </div>
                      <OnboardingTaskStatusBadge status={task.status} />
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                      {task.due_date && (
                        <div>
                          <p className="text-xs text-gray-500">Due date</p>
                          <p className="mt-0.5 text-gray-900">{formatDate(task.due_date)}</p>
                        </div>
                      )}
                      {task.completed_at && (
                        <div>
                          <p className="text-xs text-gray-500">Completed</p>
                          <p className="mt-0.5 text-gray-900">{formatDateTime(task.completed_at)}</p>
                        </div>
                      )}
                    </div>
                    {action?.href && (
                      <Link
                        href={action.href}
                        className="inline-flex bg-brand-600 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-brand-700"
                      >
                        {action.label}
                      </Link>
                    )}
                    {action?.sectionId && (
                      <button
                        type="button"
                        onClick={() => scrollToSection(action.sectionId!)}
                        className="bg-brand-600 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-brand-700"
                      >
                        {action.label}
                      </button>
                    )}
                    {action && !action.href && !action.sectionId && task.task_type === "acknowledgement" && (
                      <button
                        type="button"
                        disabled={actingId === task.id}
                        onClick={() => handleAcknowledge(task.id)}
                        className="bg-brand-600 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
                      >
                        {actingId === task.id ? "Saving..." : "Acknowledge"}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}
      </ApplicationSection>

      <div id="documents">
        <DocumentsSection
          mode="employee"
          preferredDocumentType={preferredDocumentType}
          onChanged={() => load({ silent: true })}
        />
      </div>
      <div id="trainings">
        <TrainingSection mode="employee" onChanged={() => load({ silent: true })} />
      </div>
    </div>
  );
}

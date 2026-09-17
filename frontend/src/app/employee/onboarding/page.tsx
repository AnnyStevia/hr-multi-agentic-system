"use client";

import { useCallback, useEffect, useState } from "react";
import { ApplicationSection } from "@/components/ApplicationSection";
import { OnboardingStatusBadge } from "@/components/OnboardingStatusBadge";
import { OnboardingTaskStatusBadge } from "@/components/OnboardingTaskStatusBadge";
import { useAuth } from "@/hooks/useAuth";
import { api } from "@/lib/api";
import type { Onboarding, OnboardingTask } from "@/types/onboarding";

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

export default function EmployeeOnboardingPage() {
  const { user } = useAuth();
  const [onboarding, setOnboarding] = useState<Onboarding | null>(null);
  const [tasks, setTasks] = useState<OnboardingTask[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [completingId, setCompletingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const [onboardingData, taskData] = await Promise.all([
        api.getMyOnboarding(),
        api.listMyOnboardingTasks(),
      ]);
      setOnboarding(onboardingData);
      setTasks(taskData);
    } catch (err) {
      setOnboarding(null);
      setTasks([]);
      setError(err instanceof Error ? err.message : "Failed to load onboarding");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleCompleteTask = async (taskId: number) => {
    setCompletingId(taskId);
    setError("");
    try {
      await api.completeMyOnboardingTask(taskId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to complete task");
    } finally {
      setCompletingId(null);
    }
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Welcome{user?.full_name ? `, ${user.full_name}` : ""}
        </h1>
        <p className="mt-1 text-sm text-gray-600">
          {isComplete
            ? "Your onboarding is complete. You can review your tasks below."
            : "Complete the tasks below. HR will mark your onboarding finished when everything is done."}
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
                  ? "All assigned tasks are done. Waiting for HR to complete your onboarding."
                  : `${pendingCount} pending task${pendingCount === 1 ? "" : "s"} remaining.`}
              </p>
            )}
            <div className="space-y-4">
              {tasks.map((task) => (
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
                      {task.description && (
                        <p className="mt-1 text-sm text-gray-600">{task.description}</p>
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
                  {task.status === "pending" && (
                    <button
                      type="button"
                      disabled={completingId === task.id}
                      onClick={() => handleCompleteTask(task.id)}
                      className="bg-brand-600 text-white px-3 py-2 rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
                    >
                      {completingId === task.id ? "Completing..." : "Mark as completed"}
                    </button>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </ApplicationSection>
    </div>
  );
}

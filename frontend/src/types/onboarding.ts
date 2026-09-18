export type OnboardingStatus = "in_progress" | "completed";

export type OnboardingTaskStatus = "pending" | "completed";

export type Onboarding = {
  id: number;
  employee_id: number;
  status: OnboardingStatus;
  started_at: string;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type OnboardingListItem = {
  id: number;
  employee_id: number;
  employee_name: string;
  position: string;
  status: OnboardingStatus;
  started_at: string;
  completed_at: string | null;
  completed_tasks_count: number;
  total_tasks_count: number;
};

export type OnboardingTask = {
  id: number;
  onboarding_id: number;
  title: string;
  description: string | null;
  status: OnboardingTaskStatus;
  due_date: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ProgressCount = {
  total: number;
  completed: number;
  pending: number;
};

export type OnboardingProgress = {
  onboarding_id: number;
  status: OnboardingStatus;
  completed_at: string | null;
  tasks: ProgressCount;
  trainings: ProgressCount;
  documents: { total: number };
  overall_percentage: number;
};

export type OnboardingTaskCreatePayload = {
  title: string;
  description?: string | null;
  due_date?: string | null;
};

export type OnboardingTaskUpdatePayload = {
  title?: string;
  description?: string | null;
  due_date?: string | null;
  status?: OnboardingTaskStatus;
};

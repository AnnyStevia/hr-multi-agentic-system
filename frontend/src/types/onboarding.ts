export type OnboardingStatus = "in_progress" | "completed";

export type OnboardingTaskStatus = "pending" | "completed";

export type OnboardingTaskType =
  | "profile_personal_info"
  | "profile_picture"
  | "education"
  | "experience"
  | "document"
  | "training"
  | "acknowledgement"
  | "manual";

export type EmployeeDocumentType =
  | "id_document"
  | "contract"
  | "diploma"
  | "certificate"
  | "other";

export const ONBOARDING_TASK_TYPE_LABELS: Record<OnboardingTaskType, string> = {
  profile_personal_info: "Personal info",
  profile_picture: "Profile picture",
  education: "Education",
  experience: "Experience",
  document: "Document",
  training: "Training",
  acknowledgement: "Acknowledgement",
  manual: "Manual",
};

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
  template_id?: number | null;
  title: string;
  description: string | null;
  task_type: OnboardingTaskType;
  is_required: boolean;
  document_type?: EmployeeDocumentType | null;
  training_id?: number | null;
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
  required_tasks: ProgressCount;
  optional_tasks: ProgressCount;
  trainings: ProgressCount;
  documents: { total: number };
  overall_percentage: number;
};

export type OnboardingTaskCreatePayload = {
  title: string;
  description?: string | null;
  due_date?: string | null;
  task_type?: OnboardingTaskType;
  is_required?: boolean;
  document_type?: EmployeeDocumentType | null;
  training_id?: number | null;
};

export type OnboardingTaskUpdatePayload = {
  title?: string;
  description?: string | null;
  due_date?: string | null;
  status?: OnboardingTaskStatus;
  task_type?: OnboardingTaskType;
  is_required?: boolean;
  document_type?: EmployeeDocumentType | null;
  training_id?: number | null;
};

export type OnboardingTaskTemplate = {
  id: number;
  title: string;
  description: string | null;
  task_type: OnboardingTaskType;
  is_required: boolean;
  is_active: boolean;
  document_type?: EmployeeDocumentType | null;
  training_id?: number | null;
  created_at: string;
  updated_at: string;
};

export type OnboardingTaskTemplatePayload = {
  title: string;
  description?: string | null;
  task_type: OnboardingTaskType;
  is_required?: boolean;
  is_active?: boolean;
  document_type?: EmployeeDocumentType | null;
  training_id?: number | null;
};

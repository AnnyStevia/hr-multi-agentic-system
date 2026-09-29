export type OffboardingReason =
  | "resignation"
  | "end_of_contract"
  | "termination"
  | "retirement"
  | "other";

export type OffboardingStatus =
  | "initiated"
  | "in_progress"
  | "pending_clearance"
  | "completed"
  | "cancelled";

export type OffboardingTaskCategory =
  | "documents"
  | "handover"
  | "equipment"
  | "access"
  | "administration"
  | "other";

export type OffboardingTaskStatus = "pending" | "in_progress" | "completed" | "skipped";

export const OFFBOARDING_REASON_LABELS: Record<OffboardingReason, string> = {
  resignation: "Resignation",
  end_of_contract: "End of contract",
  termination: "Termination",
  retirement: "Retirement",
  other: "Other",
};

export const OFFBOARDING_STATUS_LABELS: Record<OffboardingStatus, string> = {
  initiated: "Initiated",
  in_progress: "In progress",
  pending_clearance: "Pending clearance",
  completed: "Completed",
  cancelled: "Cancelled",
};

export const OFFBOARDING_TASK_CATEGORY_LABELS: Record<OffboardingTaskCategory, string> = {
  documents: "Documents",
  handover: "Handover",
  equipment: "Equipment",
  access: "Access",
  administration: "Administration",
  other: "Other",
};

export const OFFBOARDING_TASK_STATUS_LABELS: Record<OffboardingTaskStatus, string> = {
  pending: "Pending",
  in_progress: "In progress",
  completed: "Completed",
  skipped: "Skipped",
};

export const OFFBOARDING_TASK_CATEGORIES = Object.keys(
  OFFBOARDING_TASK_CATEGORY_LABELS,
) as OffboardingTaskCategory[];

export type OffboardingEmployeeSummary = {
  id: number;
  full_name: string;
  email: string;
  position: string;
  employee_number: string;
};

export type OffboardingCreatedBySummary = {
  id: number;
  full_name: string;
  email: string;
};

export type OffboardingListItem = {
  id: number;
  employee_id: number;
  employee_name: string;
  employee_email: string;
  position: string;
  reason: OffboardingReason;
  last_working_day: string;
  status: OffboardingStatus;
  initiated_at: string;
};

export type OffboardingDetail = {
  id: number;
  employee_id: number;
  employee: OffboardingEmployeeSummary;
  reason: OffboardingReason;
  reason_details: string | null;
  last_working_day: string;
  status: OffboardingStatus;
  initiated_at: string;
  completed_at: string | null;
  created_by: OffboardingCreatedBySummary | null;
  created_at: string;
  updated_at: string;
};

export type OffboardingEmployeeView = {
  id: number;
  status: OffboardingStatus;
  reason: OffboardingReason;
  last_working_day: string;
  initiated_at: string;
  completed_at: string | null;
};

export type OffboardingCreatePayload = {
  employee_id: number;
  reason: OffboardingReason;
  reason_details?: string | null;
  last_working_day: string;
};

export type OffboardingTaskAssignee = {
  id: number;
  full_name: string;
  email: string;
};

export type OffboardingTask = {
  id: number;
  offboarding_case_id: number;
  title: string;
  description: string | null;
  category: OffboardingTaskCategory;
  status: OffboardingTaskStatus;
  is_required: boolean;
  assigned_to_employee_id: number | null;
  assigned_to: OffboardingTaskAssignee | null;
  due_date: string | null;
  is_overdue: boolean;
  completed_at: string | null;
  completed_by_user_id: number | null;
  created_at: string;
  updated_at: string;
};

export type OffboardingTaskEmployeeView = {
  id: number;
  offboarding_case_id: number;
  title: string;
  description: string | null;
  category: OffboardingTaskCategory;
  status: OffboardingTaskStatus;
  is_required: boolean;
  due_date: string | null;
  is_overdue: boolean;
  completed_at: string | null;
};

export type OffboardingProgress = {
  offboarding_case_id: number;
  total_tasks: number;
  completed_tasks: number;
  skipped_tasks: number;
  pending_tasks: number;
  in_progress_tasks: number;
  required_total: number;
  required_completed: number;
  percentage: number;
  required_complete: boolean;
  overdue_tasks: number;
};

export type OffboardingTaskCreatePayload = {
  title: string;
  description?: string | null;
  category: OffboardingTaskCategory;
  is_required?: boolean;
  assigned_to_employee_id?: number | null;
  due_date?: string | null;
};

export type OffboardingTaskUpdatePayload = {
  title?: string;
  description?: string | null;
  category?: OffboardingTaskCategory;
  is_required?: boolean;
  assigned_to_employee_id?: number | null;
  due_date?: string | null;
  clear_assignee?: boolean;
  clear_due_date?: boolean;
};

export type OffboardingRequestStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "cancelled";

export const OFFBOARDING_REQUEST_STATUS_LABELS: Record<OffboardingRequestStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  cancelled: "Cancelled",
};

export type OffboardingRequestCreatePayload = {
  reason: "resignation" | "end_of_contract" | "retirement" | "other";
  reason_details?: string | null;
  requested_last_working_day: string;
};

export const EMPLOYEE_OFFBOARDING_REQUEST_REASONS = [
  "resignation",
  "end_of_contract",
  "retirement",
  "other",
] as const satisfies ReadonlyArray<OffboardingRequestCreatePayload["reason"]>;

export type OffboardingRequestEmployeeView = {
  id: number;
  reason: OffboardingReason;
  reason_details: string | null;
  requested_last_working_day: string;
  status: OffboardingRequestStatus;
  submitted_at: string;
  reviewed_at: string | null;
  rejection_reason: string | null;
  offboarding_case_id: number | null;
};

export type OffboardingRequestListItem = {
  id: number;
  employee_id: number;
  employee_name: string;
  employee_email: string;
  position: string;
  reason: OffboardingReason;
  requested_last_working_day: string;
  status: OffboardingRequestStatus;
  submitted_at: string;
  offboarding_case_id: number | null;
};

export type OffboardingRequestDetail = {
  id: number;
  employee_id: number;
  employee: OffboardingEmployeeSummary;
  reason: OffboardingReason;
  reason_details: string | null;
  requested_last_working_day: string;
  status: OffboardingRequestStatus;
  submitted_at: string;
  reviewed_by: OffboardingCreatedBySummary | null;
  reviewed_at: string | null;
  rejection_reason: string | null;
  offboarding_case_id: number | null;
  created_at: string;
  updated_at: string;
};

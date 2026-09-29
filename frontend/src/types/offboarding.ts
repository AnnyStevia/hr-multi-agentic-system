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

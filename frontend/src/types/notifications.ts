export type NotificationType =
  | "application_status_changed"
  | "application_submitted"
  | "interview_assignment"
  | "interview_invitation"
  | "interview_scheduled"
  | "interview_reminder"
  | "onboarding_task_assigned"
  | "onboarding_started"
  | "onboarding_task_completed"
  | "onboarding_training_assigned"
  | "onboarding_training_completed"
  | "onboarding_completed"
  | "leave_request_submitted"
  | "leave_request_manager_approved"
  | "leave_request_approved"
  | "leave_request_rejected"
  | "leave_request_cancelled";

export interface Notification {
  id: number;
  type: NotificationType;
  title: string;
  message: string;
  related_entity_type: string | null;
  related_entity_id: number | null;
  is_read: boolean;
  created_at: string;
  read_at: string | null;
}

export interface UnreadCountResponse {
  count: number;
}

export interface MarkAllReadResponse {
  updated: number;
}
